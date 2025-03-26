import json
import asyncio
import datetime
import os
import logging
import time
import tempfile
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
import sys
import ssl
from openai import AsyncAzureOpenAI
from azure.core.exceptions import ServiceRequestError
from azure.data.tables.aio import TableServiceClient, TableClient
from azure.core.exceptions import ResourceExistsError
from azure.storage.blob import BlobServiceClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

TABLE_NAME = "recallsummaries"

@dataclass
class RecallItem:
    """Class to hold recall data and processing information."""
    recall_id: str
    data: Dict[Any, Any]
    summary: str = None
    processed: bool = False
    error: str = None

async def get_table_client() -> Optional[TableClient]:
    """Create and return an Azure Table Storage client with proper error handling."""
    try:
        connection_string = os.environ.get('AZURE_STORAGE_CONNECTION_STRING')
        
        if not connection_string:
            logger.warning("Azure Storage connection string not provided. Continuing without Table Storage.")
            return None
        
        # Configure SSL context to handle certificate verification issues
        ssl_context = ssl.create_default_context()
        ssl_context.check_hostname = False
        ssl_context.verify_mode = ssl.CERT_NONE
        
        # Create the TableServiceClient using the connection string
        table_service = TableServiceClient.from_connection_string(conn_str=connection_string, connection_verify=False)
        
        # Get a client to the specific table
        table_client = table_service.get_table_client(table_name=TABLE_NAME)
        
        # Ensure the table exists
        try:
            await table_service.create_table(TABLE_NAME)
            logger.info(f"Table {TABLE_NAME} created")
        except ResourceExistsError:
            logger.info(f"Table {TABLE_NAME} already exists")
        
        logger.info("Successfully connected to Azure Table Storage")
        return table_client
    except Exception as e:
        logger.warning(f"Failed to connect to Azure Table Storage: {str(e)}. Continuing without storage.")
        return None

def create_summary_prompt(recall_data: Dict[Any, Any]) -> str:
    """Create a prompt for generating a recall summary."""
    prompt = f"""    
    Generate a recall summary in natural language with the following standardized sections for the given JSON data. 
    The summary is should be easy to render and display in html page. The tone should be informative and appropriate to the severity level.
    
    1. Recall Overview: Provide a short description of the recall event. 
    2. Product Details: Mention the product name, classification, and recall status. 
    3. Reason for Recall: Explain the reason for the recall. Provide Wikipedia link if available.
    4. Health Risks: Describe any risks associated with the issue. 
    5. Distribution & Affected Areas: Mention where the product was distributed. If mentioned "nationwide" it means across US. Otherwise specify the country and states
    6. Action Required: Provide instructions for consumers. 
    7. Additional Information: Include recall date and any other relevant details. 
    8. Reference: Provide the FDA link for further reference: https://www.fda.gov/safety/recalls-market-withdrawals-safety-alerts
    9. Contact Information: Provide the company's contact information. Do not display the contact method if it is not provided.   
    Make these main sections in bold: Recall Overview, Product Details, Reason for Recall, Health Risks, Distribution & Affected Areas, Additional Information, Reference, Contact Information. 
    Here is JSON Data: {json.dumps(recall_data, indent=2, default=str)}
    """    
    return prompt.strip()

async def generate_summary_with_retry(recall_item: RecallItem, 
                                      max_retries: int = 3, 
                                      base_delay: float = 2.0) -> RecallItem:
    """Generate a summary with exponential backoff retry for transient errors."""
    if recall_item.processed:
        return recall_item
        
    prompt = create_summary_prompt(recall_item.data)
    system_message = "You are a helpful assistant that analyzes food recall data and creates consumer-friendly summaries."
    
    # Try to read system message from file, fall back to default if not available
    try:
        with open("system.txt", "r", encoding="utf8") as f:
            system_message = f.read().strip()
    except Exception as e:
        logger.warning(f"Could not read system.txt: {str(e)}. Using default system message.")
    
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": prompt},
    ]
    
    # Get config from environment variables
    azure_oai_endpoint = os.environ.get("AZURE_OAI_ENDPOINT")
    azure_oai_key = os.environ.get("AZURE_OAI_KEY")
    azure_oai_deployment = os.environ.get("AZURE_OAI_DEPLOYMENT")
    azure_oai_api_version = os.environ.get("AZURE_OAI_API_VERSION")
    
    if not all([azure_oai_endpoint, azure_oai_key, azure_oai_deployment, azure_oai_api_version]):
        error_msg = "Missing required Azure OpenAI configuration"
        logger.error(error_msg)
        recall_item.error = error_msg
        return recall_item
    
    client = AsyncAzureOpenAI(
        azure_endpoint=azure_oai_endpoint,
        api_key=azure_oai_key,
        api_version=azure_oai_api_version
    )
    
    retry_count = 0
    while retry_count <= max_retries:
        try:
            response = await client.chat.completions.create(
                model=azure_oai_deployment,
                messages=messages,
                temperature=0.7,
                max_tokens=3000
            )
            
            recall_item.summary = response.choices[0].message.content.strip()
            recall_item.processed = True
            return recall_item
            
        except ServiceRequestError as e:
            # These are network errors that are likely transient
            retry_count += 1
            if retry_count > max_retries:
                error_msg = f"Max retries exceeded for {recall_item.recall_id}: {str(e)}"
                logger.error(error_msg)
                recall_item.error = error_msg
                return recall_item
                
            # Exponential backoff with jitter
            delay = min(60, base_delay * (2 ** (retry_count - 1))) * (0.5 + 0.5 * (time.time() % 1))
            logger.info(f"Transient error, retrying in {delay:.2f}s: {str(e)}")
            await asyncio.sleep(delay)
            
        except Exception as e:
            # Non-transient errors
            error_msg = f"Error generating summary for {recall_item.recall_id}: {str(e)}"
            logger.error(error_msg)
            recall_item.error = error_msg
            return recall_item

async def process_batch(batch: List[RecallItem], table_client: Optional[TableClient] = None) -> List[RecallItem]:
    # If table client is not available, mark all items as skipped and don't process them
    if not table_client:
        logger.warning("Skipping API calls as Table Storage is not available")
        for item in batch:
            item.processed = False
            item.error = "Skipped due to unavailable Table Storage"
        return batch

    """Process a batch of recalls."""
    if table_client:
        # Pre-check Table Storage to avoid unnecessary API calls
        for item in batch:
            if not item.processed:
                try:
                    # Query table to check if summary exists
                    query_filter = f"PartitionKey eq 'recall' and RowKey eq '{item.recall_id}'"
                    items_found = [entity async for entity in table_client.query_entities(query_filter)]
                    
                    if items_found and 'summary' in items_found[0]:
                        item.summary = items_found[0]['summary']
                        item.processed = True
                        logger.info(f"Found existing summary for {item.recall_id} in Table Storage, skipping API call")
                except Exception as e:
                    logger.warning(f"Error checking Table Storage for {item.recall_id}: {str(e)}")
    
    # Filter out already processed items
    to_process = [item for item in batch if not item.processed]
    
    if not to_process:
        return batch
    
    logger.info(f"Processing batch of {len(to_process)} recalls")
    
    # Process all items concurrently using asyncio.gather
    tasks = [generate_summary_with_retry(item) for item in to_process]
    processed_results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Handle results
    for i, result in enumerate(processed_results):
        if isinstance(result, Exception):
            logger.error(f"Error processing item: {str(result)}")
            to_process[i].error = str(result)
        else:
            to_process[i] = result
    
    # Update Table Storage with new summaries
    if table_client:
        update_tasks = []
        updates_count = 0        
        
        for item in batch:
            if item.processed and item.summary and not item.error:
                try:
                    # Create entity to insert/update
                    entity = {
                        'PartitionKey': 'recall',
                        'RowKey': item.recall_id,
                        'summary': item.summary,
                        'lastUpdated': datetime.datetime.utcnow().isoformat(),
                        'status': item.data.get('status', 'Unknown')
                    }
                    
                    # Add to tasks list
                    update_tasks.append(table_client.upsert_entity(entity=entity))
                    logger.info(f"Prepared update for {item.recall_id}")
                    updates_count += 1
                except Exception as e:
                    logger.warning(f"Error preparing entity for {item.recall_id}: {str(e)}")
                
        
        # Execute all Azure Table Storage operations in a single batch if there's anything to update
        if updates_count > 0:
            try:
                await asyncio.gather(*update_tasks, return_exceptions=True)
                logger.info(f"Updated {updates_count} summaries in Table Storage")
            except Exception as e:
                logger.error(f"Error executing Table Storage updates: {str(e)}")
    
    return batch

async def process_food_recall_data(batch_size=50):
    """
    Main function to process food recall data in batches.
    
    Args:
        batch_size: Number of recalls to process in a single batch
    """
    start_time = time.time()
    temp_file = None
    
    try:
        table_client = await get_table_client()
        if not table_client:
            logger.error("Cannot proceed without Table Storage connection")
            return False
        
        # Download file from Azure Blob Storage
        connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
        if not connection_string:
            raise ValueError("AZURE_STORAGE_CONNECTION_STRING environment variable is not set")
        
        container_name = os.environ.get("AZURE_RAW_CONTAINER", "openfda-etl")
        blob_name = os.environ.get("AZURE_RAW_BLOB", "openfda_response.json")
        
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
        
        # Create a temporary file to store the downloaded data
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json')
        download_stream = blob_client.download_blob()
        temp_file.write(download_stream.readall())
        temp_file.close()
        
        # Read the data from the temporary file
        with open(temp_file.name, 'r') as f:
            data = json.load(f)
        
        total_records = len(data)
        logger.info(f"Processing {total_records} recall records in batches of {batch_size}")
        
        # Convert data to RecallItem objects
        recall_items = []
        for i, recall in enumerate(data):
            recall_id = recall.get('recall_number', f"recall-{i}")
            recall_items.append(RecallItem(recall_id=recall_id, data=recall))
        
        # Process in batches
        results = []
        for i in range(0, len(recall_items), batch_size):
            batch = recall_items[i:i+batch_size]
            logger.info(f"Processing batch {i//batch_size + 1}/{(total_records+batch_size-1)//batch_size}")
            
            processed_batch = await process_batch(batch, table_client)            
            results.extend(processed_batch)
            
            # Add a small delay between batches to avoid rate limits
            if i + batch_size < len(recall_items):
                logger.info("Pausing between batches to avoid rate limits")
                await asyncio.sleep(10)
        
        # Log results
        successful = sum(1 for item in results if item.processed and not item.error)
        failed = sum(1 for item in results if item.error)
        skipped = sum(1 for item in results if not item.processed and not item.error)
        
        elapsed_time = time.time() - start_time
        logger.info(f"Processing complete in {elapsed_time:.2f} seconds!")
        logger.info(f"Summary: {successful} successful, {failed} failed, {skipped} skipped")
        
        # Log any errors
        for item in results:
            if item.error:
                logger.error(f"Error for {item.recall_id}: {item.error}")
        
        # Close the table client
        if table_client:
            await table_client.close()
            
        return successful > 0
                
    except Exception as e:
        logger.error(f"Error in main processing: {str(e)}", exc_info=True)
        return False
    finally:
        # Clean up the temporary file
        if temp_file and os.path.exists(temp_file.name):
            try:
                os.unlink(temp_file.name)
                logger.info(f"Cleaned up temporary file: {temp_file.name}")
            except Exception as e:
                logger.warning(f"Error cleaning up temporary file: {str(e)}")

async def main():
    """Entry point for the script."""
    success = await process_food_recall_data(batch_size=100)
    if not success:
        sys.exit(1)

if __name__ == '__main__':
    asyncio.run(main())