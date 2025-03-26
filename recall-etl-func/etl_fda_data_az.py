import os
import requests
import json
import sys
from datetime import datetime, timedelta
import io
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv
import uuid
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import tempfile

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_config():
    """Load configuration from environment variables with defaults"""
    return {
        "base_url": os.getenv("OPENFDA_BASE_URL", "https://api.fda.gov/food/enforcement.json"),
        "api_key": os.getenv("OPENFDA_API_KEY"),
        "api_limit": int(os.getenv("OPENFDA_API_LIMIT", "300")),
        "connection_string": os.getenv("AZURE_STORAGE_CONNECTION_STRING"),
        "raw_container": os.getenv("AZURE_RAW_CONTAINER", "openfda-etl"),
        "processed_container": os.getenv("AZURE_PROCESSED_CONTAINER", "openfdadata"),
        "raw_blob_name": os.getenv("AZURE_RAW_BLOB", "openfda_response.json"),
        "processed_blob_name": os.getenv("AZURE_PROCESSED_BLOB", "fda-food-enforcement-jsonl.json")
    }

def create_session_with_retries(retries=3, backoff_factor=0.5):
    """Create a requests session with retry logic"""
    session = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def convert_date(date_str):
    """Convert YYYYMMDD string to YYYY-MM-DD format if valid."""
    if date_str and isinstance(date_str, str) and len(date_str) == 8:
        try:
            return datetime.strptime(date_str, "%Y%m%d").strftime("%Y-%m-%d")
        except ValueError:
            return date_str  # Return original if conversion fails
    return date_str

def parse_fda_json_for_cognitive(data):
    """Parse FDA data for Cognitive Search indexing."""
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json', mode='w')
    output_file = temp_file.name
    count = 0
    try:
        for item in data:
            processed_item = item.copy()
            if 'openfda' in processed_item and not processed_item['openfda']:
                del processed_item['openfda']
            for date_field in ["recall_initiation_date", "center_classification_date", "report_date"]:
                if date_field in processed_item:
                    processed_item[date_field] = convert_date(processed_item[date_field])
            temp_file.write(json.dumps(processed_item) + '\n')
            count += 1
    finally:
        temp_file.close()
            
    logger.info(f"Converted {count} JSON objects to JSON lines format in {output_file}")
    return output_file
    
    
 
def fetch_openfda_data(base_url, api_key, api_limit):
    """
    Fetch data from OpenFDA API with retry logic.
    Returns a tuple of (results, request_url).
    """
    session = create_session_with_retries()
    
    # Calculate date range: today to max(100 days ago, start of current year)
    end_date = datetime.now()
    start_date = end_date - timedelta(days=100)
    year_start = datetime(end_date.year, 1, 1)
    start_date = max(start_date, year_start)

    # Format dates as YYYYMMDD
    end_date_str = end_date.strftime("%Y%m%d")
    start_date_str = start_date.strftime("%Y%m%d")
    query = f"api_key={api_key}&search=report_date:[{start_date_str}+TO+{end_date_str}]&limit={api_limit}"
    url = f"{base_url}?{query}"
    
    logger.info(f"Fetching data from OpenFDA API for date range: {start_date_str} to {end_date_str}")
    logger.info(f"Request URL: {url}")
    
    try:
        response = session.get(url, timeout=30)
        response.raise_for_status()
        data = response.json()
        results = data.get("results", [])
        logger.info(f"Successfully fetched {len(results)} records from OpenFDA API")
        return results, url
    except requests.exceptions.Timeout:
        logger.error("Request timed out. The OpenFDA API is taking too long to respond.")
        raise
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 429:
            logger.error("API rate limit exceeded. Please try again later.")
        elif e.response.status_code == 404:
            logger.error("The requested resource was not found.")
        else:
            logger.error(f"HTTP Error: {e}")
        raise
    except requests.exceptions.RequestException as e:
        logger.error(f"Error making API request: {e}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON response: {e}")
        raise

def ensure_container_exists(blob_service_client, container_name):
    """Ensure a storage container exists, create if it doesn't"""
    container_client = blob_service_client.get_container_client(container_name)
    try:
        container_properties = container_client.get_container_properties()
        logger.info(f"Container '{container_name}' already exists")
    except Exception:
        logger.info(f"Creating container '{container_name}'...")
        container_client.create_container()
        logger.info(f"Container '{container_name}' created successfully")

def upload_to_container(blob_service_client, container_name, blob_name, content):
    """
    Upload the given content to the specified container and blob name.
    Ensures the container exists before uploading.
    """
    ensure_container_exists(blob_service_client, container_name)
    
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
    
    # Check content type and handle accordingly
    if isinstance(content, str):
        blob_client.upload_blob(content, overwrite=True)
    else:
        blob_client.upload_blob(content, overwrite=True)
        
    logger.info(f"Uploaded '{blob_name}' to container '{container_name}'")

def download_parse_store_openfda_data():
    """
    Download data from OpenFDA API, parse it for Azure Cognitive Search,
    and store both the raw response and the parsed file into separate Azure storage containers.
    """
    config = get_config()
    temp_files = [] 
    
    # Validate required configuration
    if not config["api_key"]:
        logger.error("Please set the OPENFDA_API_KEY environment variable.")
        return False
        
    if not config["connection_string"]:
        logger.error("Please set the AZURE_STORAGE_CONNECTION_STRING environment variable.")
        return False

    try:
        # 1. Download openFDA data
        results, request_url = fetch_openfda_data(
            config["base_url"], 
            config["api_key"], 
            config["api_limit"]
        )
        
        if not results:
            logger.warning("No records returned from the API.")
            return False
            
        logger.info(f"Fetched {len(results)} records from the API.")
        
        # Check if recall_number is empty and assign unique numbers where needed
        for result in results:
            if 'recall_number' not in result or not result['recall_number']:
                unique_id = f"UN-ASSIGNED-{str(uuid.uuid4())[:8].upper()}"
                result['recall_number'] = unique_id
                logger.info(f"Generated unique recall number: {unique_id}")
        
        # Save raw JSON response to a temp file
        json_data = json.dumps(results, indent=4)
        
        # Create temp file for raw data
        temp_raw_file = tempfile.NamedTemporaryFile(delete=False, suffix='.json', mode='w')
        temp_raw_file.write(json_data)
        temp_raw_file.close()
        temp_files.append(temp_raw_file.name)
        logger.info(f"Saved raw response to temporary file: {temp_raw_file.name}")

        # 2. Parse the data for Azure Cognitive Search - modify the function to use temp files
        parsed_file_path = parse_fda_json_for_cognitive(results)
        temp_files.append(parsed_file_path)
        
        with open(parsed_file_path, "rb") as pf:
            parsed_content = pf.read()
       

        # 3. Upload both files into Azure Storage (different containers)
        blob_service_client = BlobServiceClient.from_connection_string(config["connection_string"])
        
        # Upload parsed file to container
        upload_to_container(
            blob_service_client, 
            config["processed_container"], 
            config["processed_blob_name"], 
            parsed_content
        )
        
        # Upload raw JSON response to container
        with open(temp_raw_file.name, "rb") as rf:
            raw_content = rf.read()
        
        upload_to_container(
            blob_service_client, 
            config["raw_container"], 
            config["raw_blob_name"], 
            raw_content
        )

        logger.info("Data download, parsing, and upload completed successfully.")
        return True

    except Exception as e:
        logger.error(f"Error in download_parse_store_openfda_data: {str(e)}", exc_info=True)
        return False
    finally:
        # Clean up temporary files
        for temp_file in temp_files:
            try:
                if os.path.exists(temp_file):
                    os.unlink(temp_file)
                    logger.info(f"Cleaned up temporary file: {temp_file}")
            except Exception as e:
                logger.warning(f"Error cleaning up temporary file {temp_file}: {str(e)}")
                

if __name__ == "__main__":
    load_dotenv()
    success = download_parse_store_openfda_data()
    if not success:
        sys.exit(1)