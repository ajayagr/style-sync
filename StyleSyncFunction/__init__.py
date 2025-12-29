import azure.functions as func
import logging
import json
import os
import requests
from azure.storage.blob import BlobServiceClient

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('StyleSync function processed a request.')

    # 1. Input Parsing
    try:
        req_body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON body"}),
            status_code=400,
            mimetype="application/json"
        )

    source_folder = req_body.get('source_folder')
    output_folder = req_body.get('output_folder')
    container_name = req_body.get('container') or os.environ.get('CONTAINER_NAME')
    styles = req_body.get('styles', [])

    if not source_folder or not output_folder or not container_name:
        return func.HttpResponse(
            json.dumps({"error": "Missing required parameters: source_folder, output_folder, container"}),
            status_code=400,
            mimetype="application/json"
        )

    # 2. Storage Connection
    connection_string = os.environ.get('AZURE_STORAGE_CONNECTION_STRING')
    if not connection_string:
        return func.HttpResponse(
            json.dumps({"error": "AZURE_STORAGE_CONNECTION_STRING not set"}),
            status_code=500,
            mimetype="application/json"
        )

    api_key = os.environ.get('AZURE_API_KEY')
    endpoint_url = os.environ.get('AZURE_ENDPOINT_URL')
    
    # We allow proceeding without API key/URL for testing storage logic, 
    # but we will log warnings and fail the styling step.
    if not api_key or not endpoint_url:
        logging.warning("AZURE_API_KEY or AZURE_ENDPOINT_URL not set. Styling will fail.")

    results = {
        "status": "completed",
        "source": f"{container_name}/{source_folder}",
        "output": f"{container_name}/{output_folder}",
        "processed": [],
        "copied": [],
        "failed": [],
        "skipped": []
    }

    try:
        blob_service_client = BlobServiceClient.from_connection_string(connection_string)
        container_client = blob_service_client.get_container_client(container_name)

        if not container_client.exists():
             return func.HttpResponse(
                json.dumps({"error": f"Container '{container_name}' does not exist"}),
                status_code=404,
                mimetype="application/json"
            )

        # 3. Processing Loop
        blobs = container_client.list_blobs(name_starts_with=source_folder)
        
        for blob in blobs:
            if blob.name.endswith('/'): # Skip directories if any
                continue
                
            blob_name = blob.name
            file_name = os.path.basename(blob_name)
            
            try:
                logging.info(f"Processing {blob_name}")
                
                # Download
                blob_client = container_client.get_blob_client(blob_name)
                download_stream = blob_client.download_blob()
                image_data = download_stream.readall()
                
                # Backup Original
                original_blob_name = f"{output_folder}original/{file_name}"
                # Check if exists to support "Incremental Processing" - assuming overwrite for now based on typical behavior, 
                # but could check existence to skip. README mentions "Skips already-processed images", 
                # usually this implies checking the *styled* output, but checking original copy is a good proxy or step.
                # For this implementation, I will just overwrite the backup to ensure consistency.
                
                backup_client = container_client.get_blob_client(original_blob_name)
                backup_client.upload_blob(image_data, overwrite=True)
                results["copied"].append(original_blob_name)
                
                # Apply Styles
                for style in styles:
                    style_name = style.get('name')
                    prompt_text = style.get('prompt_text')
                    
                    if not style_name or not prompt_text:
                        continue

                    target_blob_name = f"{output_folder}{style_name}/{file_name}"
                    
                    # Check if already processed (Incremental)
                    target_blob_client = container_client.get_blob_client(target_blob_name)
                    if target_blob_client.exists():
                        results["skipped"].append(target_blob_name)
                        continue

                    if not api_key or not endpoint_url:
                        results["failed"].append({"file": target_blob_name, "error": "API Config Missing"})
                        continue

                    # Call API
                    try:
                        # Generic multipart/form-data upload expected by many inference APIs
                        # Adjust this if the specific API expects JSON with base64
                        files = {'file': (file_name, image_data)}
                        data = {'prompt': prompt_text}
                        headers = {'x-api-key': api_key} # Common header pattern, or Authorization: Bearer
                        
                        # Note: 'x-api-key' is a guess. Often it is 'Authorization'. 
                        # I'll use a generic header dictionary that can be easily updated.
                        # For now, I will assume a header based auth or query param. 
                        # Let's try Authorization header as it's most standard, fallback or addition can be done later.
                        # Actually, looking at typical Azure AI services or standard wrappers, key often goes in header.
                        # I'll stick to 'Authorization': api_key for now.
                        api_headers = {'Authorization': api_key}
                        
                        response = requests.post(endpoint_url, files=files, data=data, headers=api_headers)
                        
                        if response.status_code == 200:
                            styled_image_data = response.content
                            target_blob_client.upload_blob(styled_image_data, overwrite=True)
                            results["processed"].append(target_blob_name)
                        else:
                            error_msg = f"API Error {response.status_code}: {response.text[:100]}"
                            logging.error(f"Failed to style {file_name} with {style_name}: {error_msg}")
                            results["failed"].append({"file": target_blob_name, "error": error_msg})

                    except Exception as api_exc:
                        logging.error(f"API Call Failed for {file_name}: {api_exc}")
                        results["failed"].append({"file": target_blob_name, "error": str(api_exc)})
            
            except Exception as e:
                logging.error(f"Error processing blob {blob_name}: {e}")
                results["failed"].append({"file": blob_name, "error": str(e)})

    except Exception as e:
        return func.HttpResponse(
            json.dumps({"error": str(e)}),
            status_code=500,
            mimetype="application/json"
        )

    return func.HttpResponse(
        json.dumps(results, indent=2),
        status_code=200,
        mimetype="application/json"
    )
