import os
import datetime
import json
import logging
import redis
import re
from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient
import azure.functions as func
from azure.storage.blob import BlobServiceClient
from typing import Dict, Any

app = func.FunctionApp()
# Initialize OpenAI client
AZURE_SEARCH_SERVICE_NAME = os.getenv("AZURE_SEARCH_SERVICE_NAME", "your-search-service")
AZURE_SEARCH_API_KEY = os.getenv("AZURE_SEARCH_API_KEY", "your-api-key")
AZURE_SEARCH_INDEX = os.getenv("AZURE_SEARCH_INDEX", "food_recall")
AZURE_SEARCH_ENDPOINT = f"https://{AZURE_SEARCH_SERVICE_NAME}.search.windows.net"
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "admin")
REDIS_CACHE_TTL = int(os.getenv("REDIS_CACHE_TTL", 3600))  # Cache TTL in seconds (default 1 hour)
AZURE_STORAGE_CONNECTION_STRING = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
ZIPCODE_BLOB_CONTAINER = os.getenv("ZIPCODE_BLOB_CONTAINER")
ZIPCODE_BLOB_NAME = os.getenv("ZIPCODE_BLOB_NAME")
# Initialize Redis client

def create_redis_client() -> redis.Redis:
    """Create and return a Redis client connection."""
    return redis.Redis(
        host='localhost',
        port=6379,
        password='admin',
        decode_responses=True  # Return strings instead of bytes
    )

def azure_redis() -> redis.Redis:
    return redis.Redis(
        host=REDIS_HOST,
        port=6380,
        password=REDIS_PASSWORD,
        ssl=True,
        ssl_cert_reqs=None,  # This disables certificate verification
        socket_timeout=5,
        socket_connect_timeout=5
    )

def load_zipcode_data():
    blob_service_client = BlobServiceClient.from_connection_string(AZURE_STORAGE_CONNECTION_STRING)
    blob_client = blob_service_client.get_blob_client(container=ZIPCODE_BLOB_CONTAINER, blob=ZIPCODE_BLOB_NAME)
    
    stream = blob_client.download_blob()
    zip_data = json.loads(stream.readall().decode('utf-8'))
 
    
    zip_to_state = {str(entry["zip"]): entry["state"] for entry in zip_data}
    city_to_state = {}
    for entry in zip_data:
        city = entry["city"].lower()
        state = entry["state"]
        if city not in city_to_state:
            city_to_state[city] = set()
        city_to_state[city].add(state)

    return zip_to_state, city_to_state
    
ZIPCODE_LOOKUP, CITY_LOOKUP = load_zipcode_data()



@app.route(route="api/recent_recalls", auth_level=func.AuthLevel.FUNCTION)
def recent_recalls(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Recent recalls from AI Search Service.')
    headers = {
        "Access-Control-Allow-Origin": "https://foodrecall-fecwdjbya4fsfxfp.eastus2-01.azurewebsites.net",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }
    try:        
        
        results = query_azure_search()
        recall_list = []
        for result in results:
            recall_list.append(result)
            
        return func.HttpResponse(
            json.dumps({
                "recalls": recall_list, 
                "count": len(recall_list),
                "query": "search_text",
                "search_type": "Recent Recalls"}),
            status_code=200,
            mimetype="application/json",
            headers=headers
            )       
    
    except Exception as e:
        logging.error(f"Error processing request: {e}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json")

@app.route(route="api/recall/{recall_id}", auth_level=func.AuthLevel.FUNCTION, methods=["GET"])
def get_recall_by_id(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Processing recall request by ID')
    recall_id = req.route_params.get('recall_id')
    
    headers = {
            "Access-Control-Allow-Origin": "https://foodrecall-fecwdjbya4fsfxfp.eastus2-01.azurewebsites.net",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        }
    
    if req.method == "OPTIONS":
        return func.HttpResponse(
            status_code=204,  # No content
            headers=headers
        )
        
    try:
        
        if not recall_id:
            return func.HttpResponse(
                    json.dumps({"error": "Recall ID is required"}),
                    status_code=400,
                    mimetype="application/json",
                    headers=headers
                )
            
            # Initialize Redis client
        redis_client = azure_redis()        
        cache_key = f"recall:summary:{recall_id}"
        cached_data = redis_client.get(cache_key)
        if cached_data:
            logging.info(f"Cache hit for recall {recall_id}")
            ai_response = cached_data.decode('utf-8')
        else:
            logging.info(f"Cache miss for recall {recall_id}")
            ai_response = "No summary available for this recall"
            
        return func.HttpResponse(
            json.dumps({
                "summary": ai_response,                 
                "query": "search_text",
                "search_type": "Recall Details"}),
            status_code=200,
            mimetype="application/json",
            headers=headers
            )         
           
                
    except Exception as e:
        logging.error(f"Error retrieving recall: {e}")
        return func.HttpResponse(
                json.dumps({"error": str(e)}),
                status_code=500,
                mimetype="application/json",
                headers=headers
            )
    
@app.route(route="api/recall_details", auth_level=func.AuthLevel.FUNCTION)
def recall_details(req: func.HttpRequest) -> func.HttpResponse:
    redis_client = azure_redis()
    headers = {
        "Access-Control-Allow-Origin": "https://foodrecall-fecwdjbya4fsfxfp.eastus2-01.azurewebsites.net",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }
    recall_number = req.params.get('recall_number')
    logging.info(f"Recall details {recall_number}")    
    
    if not recall_number:
        try:
            req_body = req.get_json()
        except ValueError:
            pass
        else:
            recall_number = req_body.get('recall_number')

    if recall_number:        
        key = f"recall:summary:{recall_number}"   
        # Try to get the recall details from Redis cache first
        cached_data = redis_client.get(key)
        if cached_data:
            logging.info(f"Cache hit for recall {recall_number}")
            ai_response = cached_data.decode('utf-8')
        else:
            logging.info(f"Cache miss for recall {recall_number}")
            ai_response = "No summary available for this recall"
        
        ## return {"recall_number": recall_number, "summary": latest_recall}
        return func.HttpResponse(
            json.dumps({
                "summary": ai_response,                 
                "query": "search_text",
                "search_type": "Recall Details"}),
            status_code=200,
            mimetype="application/json",
            headers=headers
            )
    else:
        return func.HttpResponse(
             "This HTTP triggered function executed successfully. Pass a name in the query string or in the request body for a personalized response.",
             status_code=200
        )

@app.route(route="api/search", auth_level=func.AuthLevel.FUNCTION, methods=["GET"])
def search(req: func.HttpRequest) -> func.HttpResponse:   
    
    search_text = req.params.get('q', '')
    if not search_text:
        try:
            req_body = req.get_json()
            search_text = req_body.get("q", '')
            logging.info(f"Search query params: {search_text}")
        except ValueError:
            pass
    
    results = query_azure_search(search_text)
    return func.HttpResponse(
        json.dumps(results, default=str), 
        status_code=200, 
        mimetype="application/json"
    )


def query_azure_search(search_text=""):
    try:    
        search_results = []
        search_client = SearchClient(
                endpoint=AZURE_SEARCH_ENDPOINT,
                index_name=AZURE_SEARCH_INDEX,
                credential=AzureKeyCredential(AZURE_SEARCH_API_KEY)
            )
                
        search_info = identify_search_type(search_text)
        
        if search_info["type"] == "state":
            state_values = search_info["value"]
            search_results = search_client.search(
                search_text=state_values, 
                search_fields=["distribution_pattern"],                      
                select="recall_number,reason_for_recall,status,classification,recall_initiation_date,recall_severity,product_description",
                order_by="recall_initiation_date desc",
                top=200
            )
        elif search_info["type"] == "free_text":
            search_results = search_client.search(
                search_text=search_info["value"],
                search_fields=["product_description", "reason_for_recall"],
                select="recall_number,reason_for_recall,status,classification,recall_initiation_date,recall_severity,product_description",
                order_by="recall_initiation_date desc",
                top=200
            )       
            
        return [result for result in search_results]
        
    except Exception as e:
        logging.error(f"Error querying Azure Search: {e}")
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        ) 


def identify_search_type(search_text):
    """Determine whether input is a ZIP code, state, or city."""
    search_text = search_text.strip()
    # Log the search text for debugging
    logging.info(f"Search text received: {search_text}")    

    # Check if it's a ZIP code (5-digit numeric)
    if re.match(r"^\d{5}$", search_text):
        state = ZIPCODE_LOOKUP.get(search_text)
        return {"type": "state", "value": state} if state else {"type": "unknown"}

    # Check if it's a state abbreviation (e.g., "CA")
    elif len(search_text) == 2 and search_text.upper() in set(ZIPCODE_LOOKUP.values()):
        print(f"Search type >>>>  {search_text}")
        return {"type": "state", "value": search_text.upper()}

    # Check if it's a city
    elif search_text.lower() in CITY_LOOKUP:
        states = list(CITY_LOOKUP[search_text.lower()])
        return {"type": "state", "value": states} if states else {"type": "unknown"}

    # If none of the above, treat as a free-text search
    return {"type": "free_text", "value": search_text}

