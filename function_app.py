"""
StyleSync Azure Function
HTTP-Triggered function to process images with AI style transfer.
Fully self-contained to avoid import issues.
"""
import azure.functions as func
import json
import logging
import os
import requests
import base64
import mimetypes
import time
from azure.storage.blob import BlobServiceClient
from dataclasses import dataclass
from typing import Optional, List

app = func.FunctionApp()
logger = logging.getLogger(__name__)

# ============ DATA CLASSES ============

@dataclass
class FileItem:
    name: str
    path: str
    is_dir: bool = False

@dataclass
class GeneratorResult:
    data: Optional[bytes]
    request_info: str = ""
    response_info: str = ""

# ============ STORAGE PROVIDER ============

class AzureBlobProvider:
    def __init__(self, connection_string: str, container_name: str):
        self.blob_service = BlobServiceClient.from_connection_string(connection_string)
        self.container = self.blob_service.get_container_client(container_name)
        if not self.container.exists():
            self.container.create_container()
    
    def exists(self, path: str) -> bool:
        if not path:
            return True  # Root always exists
        return self.container.get_blob_client(path).exists()
    
    def list_files(self, prefix: str = "") -> List[FileItem]:
        blobs = self.container.list_blobs(name_starts_with=prefix if prefix else None)
        return [FileItem(name=b.name.rsplit("/", 1)[-1], path=b.name) for b in blobs]
    
    def read_file(self, path: str) -> bytes:
        return self.container.get_blob_client(path).download_blob().readall()
    
    def write_file(self, path: str, data: bytes):
        self.container.get_blob_client(path).upload_blob(data, overwrite=True)

# ============ SYNC LOGIC ============

def get_valid_images(provider: AzureBlobProvider, source_dir: str):
    valid_extensions = {'.jpg', '.jpeg', '.png', '.webp'}
    for item in provider.list_files(source_dir):
        if not item.is_dir and any(item.name.lower().endswith(ext) for ext in valid_extensions):
            yield item

def map_expected_state(provider: AzureBlobProvider, source_dir: str, styles: list):
    expected_state = {}
    valid_images = list(get_valid_images(provider, source_dir))
    
    for item in valid_images:
        # Original copy
        original_key = f"original/{item.name}"
        expected_state[original_key] = {
            'source_item': item,
            'style': None,
            'output_path': original_key,
            'is_original': True
        }
        
        # Styled variants
        for style in styles:
            style_name = style.get('name', f"style_{style['index']}")
            style_folder = style_name.replace(' ', '_').lower()
            style_key = f"{style_folder}/{item.name}"
            expected_state[style_key] = {
                'source_item': item,
                'style': style,
                'output_path': style_key,
                'is_original': False
            }
    
    return expected_state

def get_missing_files(provider: AzureBlobProvider, expected_state: dict, output_dir: str):
    missing = []
    for rel_path, details in expected_state.items():
        target = f"{output_dir.rstrip('/')}/{rel_path}"
        if not provider.exists(target):
            details_copy = details.copy()
            details_copy['full_target_path'] = target
            missing.append(details_copy)
    return missing

# ============ AI GENERATOR ============

def process_image_azure(image_data: bytes, filename: str, prompt: str, strength: float) -> GeneratorResult:
    endpoint = os.environ.get("AZURE_ENDPOINT_URL")
    api_key = os.environ.get("AZURE_API_KEY")
    
    if not endpoint or not api_key:
        return GeneratorResult(None, "Missing config", "AZURE_ENDPOINT_URL or AZURE_API_KEY not set")
    
    headers = {"Authorization": f"Bearer {api_key}"}
    mime_type, _ = mimetypes.guess_type(filename)
    if not mime_type:
        mime_type = "image/png"
    
    try:
        files = {"image": (filename, image_data, mime_type)}
        data = {"model": "flux.1-kontext-pro", "prompt": prompt}
        
        response = requests.post(endpoint, headers=headers, files=files, data=data, timeout=120)
        response.raise_for_status()
        
        result = response.json()
        if "data" in result and len(result["data"]) > 0:
            item = result["data"][0]
            if item.get("b64_json"):
                return GeneratorResult(base64.b64decode(item["b64_json"]))
            elif item.get("url"):
                img_resp = requests.get(item['url'])
                return GeneratorResult(img_resp.content)
        
        return GeneratorResult(None, "API call", "No data in response")
    except Exception as e:
        return GeneratorResult(None, "API call", str(e))

# ============ FUNCTION ENTRY POINT ============

@app.function_name(name="stylesync")
@app.route(route="stylesync", auth_level=func.AuthLevel.ANONYMOUS, methods=["POST"])
def main(req: func.HttpRequest) -> func.HttpResponse:
    logger.info("StyleSync function triggered.")
    
    try:
        req_body = req.get_json()
    except ValueError:
        return func.HttpResponse(json.dumps({"error": "Invalid JSON"}), status_code=400, mimetype="application/json")
    
    # Parameters
    container = req_body.get("container", os.environ.get("CONTAINER_NAME", "file-container"))
    source_folder = req_body.get("source_folder", "")
    output_folder = req_body.get("output_folder", "styled/")
    styles = req_body.get("styles", [])
    
    if not styles:
        return func.HttpResponse(json.dumps({"error": "No styles provided"}), status_code=400, mimetype="application/json")
    
    # Storage
    conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not conn_str:
        return func.HttpResponse(json.dumps({"error": "Storage not configured"}), status_code=500, mimetype="application/json")
    
    storage = AzureBlobProvider(conn_str, container)
    
    results = {"status": "completed", "processed": [], "failed": [], "skipped": []}
    
    try:
        expected = map_expected_state(storage, source_folder, styles)
        tasks = get_missing_files(storage, expected, output_folder)
        
        logger.info(f"Expected: {len(expected)}, Tasks: {len(tasks)}")
        
        for task in tasks:
            source_item = task['source_item']
            is_original = task.get('is_original', False)
            target_path = task.get('full_target_path')
            output_path = task.get('output_path', '')
            
            try:
                input_data = storage.read_file(source_item.path)
                
                if is_original:
                    storage.write_file(target_path, input_data)
                    results["processed"].append(f"original/{source_item.name}")
                else:
                    style = task['style']
                    result = process_image_azure(input_data, source_item.name, style['prompt_text'], style['strength'])
                    
                    if result and result.data:
                        storage.write_file(target_path, result.data)
                        results["processed"].append(output_path)
                    else:
                        results["failed"].append(output_path)
            except Exception as e:
                logger.error(f"Error: {output_path} - {e}")
                results["failed"].append(output_path)
        
        results["skipped"] = [k for k in expected.keys() if k not in [t.get('output_path', '') for t in tasks]]
        
    except Exception as e:
        logger.error(f"Critical: {e}")
        results["status"] = "failed"
        results["error"] = str(e)
    
    return func.HttpResponse(json.dumps(results, indent=2), status_code=200 if results["status"] == "completed" else 500, mimetype="application/json")
