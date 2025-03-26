import os
import sys
import logging
import time
from azure.search.documents.indexes import SearchIndexerClient
from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import ResourceNotFoundError, HttpResponseError
from dotenv import load_dotenv

# Set up logging - use only console output
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("etl_az_indexer")

def get_config():
    """Load and validate configuration from environment variables."""
    # Load environment variables
    load_dotenv()
    
    config = {
        "search_service_name": os.getenv("AZURE_SEARCH_SERVICE_NAME"),
        "search_api_key": os.getenv("AZURE_SEARCH_API_KEY"),
        "indexer_name": os.getenv("AZURE_SEARCH_INDEXER_NAME"),
    }
    
    # Validate required configuration
    missing_vars = [k for k, v in config.items() if not v]
    if missing_vars:
        error_msg = f"Missing required environment variables: {', '.join(missing_vars)}"
        logger.error(error_msg)
        return None
    
    # Derive endpoint from service name
    config["search_endpoint"] = f"https://{config['search_service_name']}.search.windows.net"
    
    return config

def get_indexer_client(endpoint, api_key):
    """Create and return a SearchIndexerClient."""
    try:
        return SearchIndexerClient(
            endpoint=endpoint,
            credential=AzureKeyCredential(api_key),
            retry_policy=None,
            logging_enable=True,
            max_retries=3
        )
    except Exception as e:
        logger.error(f"Failed to create search indexer client: {str(e)}")
        return None

def check_indexer_status(client, indexer_name, max_wait_seconds=120):
    """Check the status of the indexer and wait until it's completed or failed."""
    wait_time = 0
    sleep_interval = 10
    
    while wait_time < max_wait_seconds:
        try:
            status = client.get_indexer_status(indexer_name)
            
            if status.last_result:
                if status.last_result.status == "success":
                    logger.info(f"Indexer completed successfully. Items processed: {status.last_result.item_count}, Failed: {status.last_result.failed_item_count}")
                    return True
                elif status.last_result.status in ["transientFailure", "persistentFailure"]:
                    logger.error(f"Indexer failed with status: {status.last_result.status}. Error message: {status.last_result.error_message}")
                    return False
            
            # If still running or pending, wait and check again
            logger.info(f"Indexer status: {status.status}. Waiting {sleep_interval} seconds...")
            time.sleep(sleep_interval)
            wait_time += sleep_interval
            
        except Exception as e:
            logger.error(f"Error checking indexer status: {str(e)}")
            return False
    
    logger.warning(f"Timed out after waiting {max_wait_seconds} seconds for indexer to complete")
    return False

async def run_indexer(check_status=True, max_wait_seconds=120):
    """Run the Azure Search indexer and check its status."""
    # Get configuration
    config = get_config()
    if not config:
        return False
    
    try:
        # Create a client
        client = get_indexer_client(config["search_endpoint"], config["search_api_key"])
        if not client:
            return False
        
        # Run the indexer
        logger.info(f"Starting indexer '{config['indexer_name']}'...")
        client.run_indexer(config["indexer_name"])
        
        # Check indexer status if requested
        if check_status:
            success = check_indexer_status(client, config["indexer_name"], max_wait_seconds)
            
            if success:
                logger.info("ETL indexer process completed successfully.")
                return True
            else:
                logger.error("ETL indexer process failed.")
                return False
        else:
            logger.info("Indexer started. Status checking skipped.")
            return True
            
    except ResourceNotFoundError as e:
        logger.error(f"Indexer not found: {str(e)}")
        return False
    except HttpResponseError as e:
        logger.error(f"HTTP error when running indexer: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        return False

if __name__ == "__main__":
    logger.info("Starting Azure Search indexer ETL process...")
    import asyncio
    success = asyncio.run(run_indexer())
    exit_code = 0 if success else 1
    logger.info(f"Exiting with code {exit_code}")
    sys.exit(exit_code)