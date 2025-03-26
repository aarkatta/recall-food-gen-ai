import azure.functions as func
import datetime
import json
import logging
from etl_fda_data_az import download_parse_store_openfda_data

app = func.FunctionApp()

@app.route(route="etl_fda_data", auth_level=func.AuthLevel.FUNCTION)
def etl_fda_data(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Open FDA Food Recall data extraction function triggered.')
    try :
        success = download_parse_store_openfda_data()
        if success:
            return func.HttpResponse(
                "Open FDA Food Recall data extraction completed successfully.",
                status_code=200
            )
        else:
            return func.HttpResponse(
                "Open FDA Food Recall data extraction process failed. Check the logs for details.",
                status_code=500
            )
    except Exception as e:
        error_message = str(e)
        logging.error(f"Error during ETL process: {error_message}")
        return func.HttpResponse(
            f"Error during FDA data extraction: {error_message}",
            status_code=500
        )
    

    

@app.route(route="etl_fda_gen_summary", auth_level=func.AuthLevel.FUNCTION)
async def etl_fda_gen_summary(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Starting OpenAI summary generation process.')
    
    try:
        # Import the async function from your script
        from etl_az_openai_gen_ai import process_food_recall_data
        
        # Call the async function
        success = await process_food_recall_data(batch_size=50)
        
        if success:
            return func.HttpResponse(
                "OpenAI summary generation completed successfully.",
                status_code=200
            )
        else:
            return func.HttpResponse(
                "OpenAI summary generation failed. Check the logs for details.",
                status_code=500
            )
    except Exception as e:
        error_message = str(e)
        logging.error(f"Error in OpenAI summary generation: {error_message}", exc_info=True)
        return func.HttpResponse(
            f"Error: {error_message}",
            status_code=500
        )

@app.route(route="etl_fda_indexer", auth_level=func.AuthLevel.FUNCTION)
async def etl_fda_indexer(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('FDA Indexer ETL Azure Function processing request.')
    
    try:
        # Import the async function from your script
        from etl_az_indexer import run_indexer
        
        # Check if we should skip status checking
        skip_status = req.params.get('skip_status')
        check_status = not (skip_status and skip_status.lower() in ('true', 'yes', '1'))
        
        # Get max wait time if provided
        max_wait_seconds = req.params.get('max_wait_seconds')
        if max_wait_seconds:
            try:
                max_wait_seconds = int(max_wait_seconds)
            except ValueError:
                max_wait_seconds = 120
        else:
            max_wait_seconds = 120
        
        # Call the async function
        success = await run_indexer(check_status=check_status, max_wait_seconds=max_wait_seconds)
        
        if success:
            status_info = "completed" if check_status else "started"
            return func.HttpResponse(
                f"Azure Search indexer {status_info} successfully.",
                status_code=200
            )
        else:
            return func.HttpResponse(
                "Azure Search indexer operation failed. Check the logs for details.",
                status_code=500
            )
    except Exception as e:
        error_message = str(e)
        logging.error(f"Error in ETL indexer operation: {error_message}", exc_info=True)
        return func.HttpResponse(
            f"Error: {error_message}",
            status_code=500
        )