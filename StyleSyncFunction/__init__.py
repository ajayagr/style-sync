"""
StyleSync Azure Function - Image Style Transfer
HTTP-triggered function that processes images from Azure Blob Storage
and applies AI style transformations.
"""
import azure.functions as func
import json
import logging
import os
import requests
import base64
import mimetypes
from azure.storage.blob import BlobServiceClient
from dataclasses import dataclass
from typing import Optional, List


# ==================== DATA CLASSES ====================

@dataclass
class FileItem:
    """Represents a file in storage."""
    name: str
    path: str
    is_dir: bool = False


# ==================== AZURE BLOB STORAGE ====================

class BlobStorageProvider:
    """Azure Blob Storage operations."""
    
    def __init__(self, connection_string: str, container_name: str):
        self.client = BlobServiceClient.from_connection_string(connection_string)
        self.container = self.client.get_container_client(container_name)
        if not self.container.exists():
            self.container.create_container()
    
    def exists(self, path: str) -> bool:
        if not path:
            return True
        return self.container.get_blob_client(path).exists()
    
    def list_files(self, prefix: str = "") -> List[FileItem]:
        blobs = self.container.list_blobs(name_starts_with=prefix if prefix else None)
        return [FileItem(name=b.name.rsplit("/", 1)[-1], path=b.name) for b in blobs]
    
    def read_file(self, path: str) -> bytes:
        return self.container.get_blob_client(path).download_blob().readall()
    
    def write_file(self, path: str, data: bytes):
        self.container.get_blob_client(path).upload_blob(data, overwrite=True)


# ==================== IMAGE PROCESSING ====================

VALID_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}


def get_images(storage: BlobStorageProvider, source_dir: str) -> List[FileItem]:
    """Get valid image files from source directory."""
    return [
        item for item in storage.list_files(source_dir)
        if not item.is_dir and any(item.name.lower().endswith(ext) for ext in VALID_EXTENSIONS)
    ]


def process_image_with_ai(image_data: bytes, filename: str, prompt: str) -> Optional[bytes]:
    """Apply AI style transformation using Azure endpoint."""
    endpoint = os.environ.get("AZURE_ENDPOINT_URL")
    api_key = os.environ.get("AZURE_API_KEY")
    
    if not endpoint or not api_key:
        logging.error("AZURE_ENDPOINT_URL or AZURE_API_KEY not configured")
        return None
    
    mime_type, _ = mimetypes.guess_type(filename)
    if not mime_type:
        mime_type = "image/png"
    
    try:
        response = requests.post(
            endpoint,
            headers={"Authorization": f"Bearer {api_key}"},
            files={"image": (filename, image_data, mime_type)},
            data={"model": "flux.1-kontext-pro", "prompt": prompt},
            timeout=120
        )
        response.raise_for_status()
        
        result = response.json()
        if "data" in result and len(result["data"]) > 0:
            item = result["data"][0]
            if item.get("b64_json"):
                return base64.b64decode(item["b64_json"])
            elif item.get("url"):
                img_resp = requests.get(item["url"], timeout=60)
                return img_resp.content
    except Exception as e:
        logging.error(f"AI processing error: {e}")
    
    return None


# ==================== MAIN FUNCTION ====================

def main(req: func.HttpRequest) -> func.HttpResponse:
    """
    HTTP trigger for StyleSync.
    
    Request body:
    {
        "source_folder": "originals/",
        "output_folder": "styled/",
        "container": "file-container",
        "styles": [
            {"name": "geometric_3d", "prompt_text": "Turn into geometric 3D art"}
        ]
    }
    """
    logging.info("StyleSync function triggered")
    
    # Parse request
    try:
        body = req.get_json()
    except ValueError:
        return func.HttpResponse(
            json.dumps({"error": "Invalid JSON body"}),
            status_code=400,
            mimetype="application/json"
        )
    
    # Get parameters
    container = body.get("container", os.environ.get("CONTAINER_NAME", "file-container"))
    source_folder = body.get("source_folder", "")
    output_folder = body.get("output_folder", "styled/")
    styles = body.get("styles", [])
    
    if not styles:
        return func.HttpResponse(
            json.dumps({"error": "No styles provided"}),
            status_code=400,
            mimetype="application/json"
        )
    
    # Initialize storage
    conn_str = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
    if not conn_str:
        return func.HttpResponse(
            json.dumps({"error": "AZURE_STORAGE_CONNECTION_STRING not configured"}),
            status_code=500,
            mimetype="application/json"
        )
    
    storage = BlobStorageProvider(conn_str, container)
    
    # Process images
    results = {
        "status": "completed",
        "source": f"{container}/{source_folder}",
        "output": f"{container}/{output_folder}",
        "processed": [],
        "copied": [],
        "failed": [],
        "skipped": []
    }
    
    try:
        images = get_images(storage, source_folder)
        logging.info(f"Found {len(images)} images")
        
        for image in images:
            # Copy original
            original_path = f"{output_folder.rstrip('/')}/original/{image.name}"
            if not storage.exists(original_path):
                try:
                    data = storage.read_file(image.path)
                    storage.write_file(original_path, data)
                    results["copied"].append(f"original/{image.name}")
                except Exception as e:
                    logging.error(f"Copy error: {e}")
                    results["failed"].append(f"original/{image.name}")
            else:
                results["skipped"].append(f"original/{image.name}")
            
            # Apply styles
            for style in styles:
                style_name = style.get("name", "styled")
                style_folder = style_name.replace(" ", "_").lower()
                style_path = f"{output_folder.rstrip('/')}/{style_folder}/{image.name}"
                
                if storage.exists(style_path):
                    results["skipped"].append(f"{style_folder}/{image.name}")
                    continue
                
                try:
                    data = storage.read_file(image.path)
                    styled = process_image_with_ai(data, image.name, style.get("prompt_text", ""))
                    
                    if styled:
                        storage.write_file(style_path, styled)
                        results["processed"].append(f"{style_folder}/{image.name}")
                    else:
                        results["failed"].append(f"{style_folder}/{image.name}")
                except Exception as e:
                    logging.error(f"Style error: {e}")
                    results["failed"].append(f"{style_folder}/{image.name}")
    
    except Exception as e:
        logging.error(f"Critical error: {e}")
        results["status"] = "failed"
        results["error"] = str(e)
    
    status_code = 200 if results["status"] == "completed" else 500
    return func.HttpResponse(
        json.dumps(results, indent=2),
        status_code=status_code,
        mimetype="application/json"
    )
