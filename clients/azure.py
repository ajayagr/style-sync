import logging
import os
import requests
import base64
import json
from pathlib import Path
from .base import ImageGenerator

logger = logging.getLogger(__name__)

class AzureGenerator(ImageGenerator):
    def process_image(self, image_path, prompt, strength):
        endpoint = os.environ.get("AZURE_ENDPOINT_URL")
        api_key = os.environ.get("AZURE_API_KEY")

        if not endpoint or not api_key:
            raise ValueError("Environment variables AZURE_ENDPOINT_URL and AZURE_API_KEY must be set.")
            
        logger.info(f"Using Endpoint: {endpoint}")

        # The curl command implies multipart/form-data with Authorization: Bearer
        headers = {
            "Authorization": f"Bearer {api_key}"
            # No Content-Type, requests adds it for multipart
        }

        # Determine mime type
        import mimetypes
        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type:
            mime_type = "image/png" 

        try:
             with open(image_path, "rb") as f:
                 file_content = f.read()

             # Multipart Form Data
             # -F "model=flux.1-kontext-pro"
             # -F "image=@image_to_edit.png"
             # -F "prompt=..."
             
             files = {
                 "image": (image_path.name, file_content, mime_type)
             }
             
             data = {
                 "model": "flux.1-kontext-pro",
                 "prompt": prompt
                 # Note: User's curl command did NOT include strength.
                 # If this model supports strength, it might be via "strength" or "image_strength".
                 # I will omit it for now to match exactly the working curl command first.
             }

             logger.info(f"Submitting request for {image_path.name}...")
             response = requests.post(endpoint, headers=headers, files=files, data=data)
             response.raise_for_status()

             # User's command: jq -r '.data[0].b64_json'
             result = response.json()
             
             if "data" in result and len(result["data"]) > 0:
                 item = result["data"][0]
                 if "b64_json" in item:
                     return base64.b64decode(item["b64_json"])
                 if "url" in item:
                     logger.info(f"Result is URL, downloading from {item['url']}...")
                     img_resp = requests.get(item['url'])
                     img_resp.raise_for_status()
                     return img_resp.content

             logger.error(f"Unexpected response structure: {list(result.keys())}")
             return None

        except requests.exceptions.HTTPError as e:
            logger.error(f"API Error processing {image_path}: {e}")
            if e.response is not None:
                 logger.error(f"Response content: {e.response.text}")
            return None
        except Exception as e:
            logger.error(f"Error processing {image_path}: {e}")
            return None
