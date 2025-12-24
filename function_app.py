"""
StyleSync Azure Function
HTTP-Triggered function to process images with AI style transfer.
Pulls from source folder in File Bucket storage, outputs to target folder.
"""
import azure.functions as func
import json
import logging
import os
from azure.storage.blob import BlobServiceClient

# Import StyleSync core logic
from sync import map_expected_state, get_missing_files
from clients import get_generator
from config import load_config

logger = logging.getLogger(__name__)

# Azure Blob Storage Provider (inline for simplicity)
class AzureBlobProvider:
    def __init__(self, connection_string: str, container_name: str):
        self.blob_service = BlobServiceClient.from_connection_string(connection_string)
        self.container = self.blob_service.get_container_client(container_name)
        if not self.container.exists():
            self.container.create_container()
    
    def exists(self, path: str) -> bool:
        return self.container.get_blob_client(path).exists()
    
    def list_files(self, prefix: str = ""):
        from dataclasses import dataclass
        @dataclass
        class FileItem:
            name: str
            path: str
            is_dir: bool = False
        
        blobs = self.container.list_blobs(name_starts_with=prefix)
        return [FileItem(name=b.name.rsplit("/", 1)[-1], path=b.name) for b in blobs]
    
    def read_file(self, path: str) -> bytes:
        return self.container.get_blob_client(path).download_blob().readall()
    
    def write_file(self, path: str, data: bytes):
        self.container.get_blob_client(path).upload_blob(data, overwrite=True)
    
    def mkdir(self, path: str):
        pass  # No-op for blob storage


app = func.FunctionApp()

@app.function_name(name="stylesync")
@app.route(route="stylesync", auth_level=func.AuthLevel.FUNCTION, methods=["POST"])
def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    HTTP Trigger handler for StyleSync.
    
    Expected JSON body:
    {
        "source_folder": "originals/",
        "output_folder": "styled/",
        "container": "file-container",
        "provider": "azure",
        "styles": [{"index": 1, "name": "Watercolor", "prompt_text": "...", "strength": 0.7}]
    }
    """
    logger.info("StyleSync function triggered.")
    
    try:
        req_body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON body"}),
            status_code=400,
            mimetype="application/json"
        )
    
    # Extract parameters
    container = req_body.get("container", os.environ.get("CONTAINER_NAME", "file-container"))
    source_folder = req_body.get("source_folder", "originals/")
    output_folder = req_body.get("output_folder", "styled/")
    styles = req_body.get("styles", [])
    provider_name = req_body.get("provider", "azure")
    
    # Load default styles from config if not provided
    if not styles:
        try:
            config = load_config("config.yaml")
            styles = config.get("styles", [])
        except Exception as e:
            logger.warning(f"Could not load config.yaml: {e}")
    
    if not styles:
        return func.HttpResponse(
            json.dumps({"error": "No styles provided and config.yaml not found"}),
            status_code=400,
            mimetype="application/json"
        )
    
    # Initialize Storage
    connection_string = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not connection_string:
        return func.HttpResponse(
            json.dumps({"error": "AZURE_STORAGE_CONNECTION_STRING not configured"}),
            status_code=500,
            mimetype="application/json"
        )
    
    storage = AzureBlobProvider(connection_string, container)
    
    # Initialize Generator
    try:
        generator = get_generator(provider_name)
    except ValueError as e:
        return func.HttpResponse(
            json.dumps({"error": f"Generator error: {e}"}),
            status_code=500,
            mimetype="application/json"
        )
    
    # Results
    results = {
        "status": "completed",
        "source": f"{container}/{source_folder}",
        "output": f"{container}/{output_folder}",
        "processed": [],
        "failed": [],
        "skipped": []
    }
    
    try:
        # Map Expected State
        expected = map_expected_state(storage, source_folder, styles)
        
        # Get Missing Files
        tasks = get_missing_files(storage, expected, output_folder)
        
        logger.info(f"Expected: {len(expected)}, Tasks: {len(tasks)}")
        
        for task in tasks:
            source_item = task['source_item']
            style = task['style']
            output_filename = task['output_filename']
            
            try:
                # Read Source
                input_data = storage.read_file(source_item.path)
                
                # Generate Styled Image
                result = generator.process_image_bytes(
                    input_data,
                    source_item.name,
                    style['prompt_text'],
                    style['strength']
                )
                
                if result and result.data:
                    # Write to Output
                    target_path = f"{output_folder.rstrip('/')}/{output_filename}"
                    storage.write_file(target_path, result.data)
                    results["processed"].append(output_filename)
                else:
                    results["failed"].append(output_filename)
                    
            except Exception as e:
                logger.error(f"Error processing {output_filename}: {e}")
                results["failed"].append(output_filename)
        
        # Skipped = already existed
        results["skipped"] = [k for k in expected.keys() if k not in [t['output_filename'] for t in tasks]]
        
    except Exception as e:
        logger.error(f"Critical error: {e}")
        results["status"] = "failed"
        results["error"] = str(e)
    
    return func.HttpResponse(
        json.dumps(results, indent=2),
        status_code=200 if results["status"] == "completed" else 500,
        mimetype="application/json"
    )
