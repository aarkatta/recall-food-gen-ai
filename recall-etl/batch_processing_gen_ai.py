import json
import datetime
import redis
import openai
import os
from typing import Dict, Any, List
import logging
import asyncio
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

# Configure OpenAI API key
openai.api_key = os.environ.get("OPENAI_API_KEY")
if not openai.api_key:
    raise ValueError("Open API Key is not set. Please set the OPENAI_API_KEY environment variable.")

local_redis_host = os.getenv('LOCAL_REDIS_HOST', '')
local_redis_password = os.getenv('LOCAL_REDIS_PASSWORD', '')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class RecallItem:
    """Class to hold recall data and processing information."""
    recall_id: str
    data: Dict[Any, Any]
    summary: str = None
    processed: bool = False
    error: str = None


# Create Redis client
def create_redis_client() -> redis.Redis:
    """Create and return a Redis client connection."""
    return redis.Redis(
        host=local_redis_host,
        port=6379,
        password=local_redis_password,
        decode_responses=True  # Return strings instead of bytes
    )


# Create a prompt method (unchanged)
def create_summary_prompt(recall_data: Dict[Any, Any]) -> str:
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


# Send data to OpenAI and generate summary
def generate_summary(recall_item: RecallItem) -> RecallItem:
    """Generate a summary of the recall data using OpenAI."""
    try:
        # Skip if already in Redis (will be checked in the main function)
        if recall_item.processed:
            return recall_item
            
        prompt = create_summary_prompt(recall_item.data)
        
        response = openai.chat.completions.create(
            model="gpt-4o", 
            messages=[
                {"role": "system", "content": "You are a helpful assistant that summarizes food recall information."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=3000,
            temperature=0.5
        )
        
        recall_item.summary = response.choices[0].message.content.strip()
        recall_item.processed = True
        
        return recall_item
    except Exception as e:
        error_msg = f"Error generating summary for {recall_item.recall_id}: {str(e)}"
        logger.error(error_msg)
        recall_item.error = error_msg
        return recall_item


# Process a batch of recalls with proper error handling and retries
def process_batch(batch: List[RecallItem], redis_client: redis.Redis = None) -> List[RecallItem]:
    """Process a batch of recalls using a thread pool."""
    if redis_client:
        # Pre-check Redis to avoid unnecessary API calls
        for item in batch:
            key = f"recall:summary:{item.recall_id}"
            if redis_client.exists(key):
                item.processed = True
                item.summary = redis_client.get(key)
                logger.info(f"Found existing summary for {item.recall_id} in Redis, skipping API call")
    
    # Filter out already processed items
    to_process = [item for item in batch if not item.processed]
    
    if not to_process:
        return batch
    
    logger.info(f"Processing batch of {len(to_process)} recalls")
    
    # Use a thread pool to process the batch
    with ThreadPoolExecutor(max_workers=10) as executor:
        # Submit all tasks
        future_to_item = {executor.submit(generate_summary, item): item for item in to_process}
        
        # Handle results as they complete
        for future in future_to_item:
            try:
                # This will propagate any exceptions from the future
                future.result()
            except Exception as e:
                item = future_to_item[future]
                logger.error(f"Failed to process {item.recall_id}: {str(e)}")
                item.error = str(e)
    
    # Update Redis with new summaries
    if redis_client:
        pipe = redis_client.pipeline()
        for item in batch:
            if item.processed and item.summary and not item.error:
                key_summary = f"recall:summary:{item.recall_id}"
                key_data = f"recall:data:{item.recall_id}"
                pipe.set(key_summary, item.summary)
                pipe.set(key_data, json.dumps(item.data, default=str))
        
        # Execute all Redis operations in a single batch
        if pipe:
            pipe.execute()
    
    return batch


# Main function to process the data
def process_food_recall_data(batch_size=50):
    """
    Main function to process food recall data in batches.
    
    Args:
        batch_size: Number of recalls to process in a single batch
    """
    try:
        start_time = time.time()
        redis_client = create_redis_client()
        
        # Read the data file
        with open('response.json', 'r') as file:
            data = json.load(file)
        
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
            
            processed_batch = process_batch(batch, redis_client)
            results.extend(processed_batch)
            
            # Add a small delay between batches to avoid rate limits
            if i + batch_size < len(recall_items):
                logger.info("Pausing between batches to avoid rate limits")
                time.sleep(60)
        
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
                
    except Exception as e:
        logger.error(f"Error in main processing: {str(e)}", exc_info=True)


if __name__ == "__main__":
    # You can adjust the batch size based on your API rate limits and needs
    process_food_recall_data(batch_size=50)