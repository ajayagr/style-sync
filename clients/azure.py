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
        import time
        from .base import ImageGenerationResult

        endpoint = os.environ.get("AZURE_ENDPOINT_URL")
        api_key = os.environ.get("AZURE_API_KEY")

        if not endpoint or not api_key:
            raise ValueError("Environment variables AZURE_ENDPOINT_URL and AZURE_API_KEY must be set.")
            
        logger.info(f"Using Endpoint: {endpoint}")

        headers = {
            "Authorization": f"Bearer {api_key}"
        }

        # Determine mime type
        import mimetypes
        mime_type, _ = mimetypes.guess_type(image_path)
        if not mime_type:
            mime_type = "image/png" 

        start_time = time.time()
        req_info = f"POST {endpoint}\nData: model=flux.1-kontext-pro, prompt={prompt[:50]}..."
        resp_info = ""
        
        try:
             with open(image_path, "rb") as f:
                 file_content = f.read()

             # Multipart Form Data
             files = {
                 "image": (image_path.name, file_content, mime_type)
             }
             
             data = {
                 "model": "flux.1-kontext-pro",
                 "prompt": prompt
             }

             logger.info(f"Submitting request for {image_path.name}...")
             response = requests.post(endpoint, headers=headers, files=files, data=data)
             
             latency = time.time() - start_time
             resp_info = f"Status: {response.status_code}\nHeaders: {dict(response.headers)}"
             
             response.raise_for_status()

             result = response.json()
             
             image_data = None
             if "data" in result and len(result["data"]) > 0:
                 item = result["data"][0]
                 
                 # Prioritize Base64
                 if item.get("b64_json"):
                     image_data = base64.b64decode(item["b64_json"])
                 # Fallback to URL if Base64 not present
                 elif item.get("url"):
                     logger.info(f"Result is URL, downloading from {item['url']}...")
                     img_resp = requests.get(item['url'])
                     img_resp.raise_for_status()
                     image_data = img_resp.content

             if image_data:
                 return ImageGenerationResult(
                     data=image_data,
                     latency=latency,
                     request_info=req_info,
                     response_info=resp_info
                 )

             logger.error(f"Unexpected response structure: {list(result.keys())}")
             # Return failure result but with logs
             return ImageGenerationResult(None, latency, req_info, resp_info + f"\nError: Unexpected structure")
 
        except requests.exceptions.HTTPError as e:
            latency = time.time() - start_time
            logger.error(f"API Error processing {image_path}: {e}")
            error_details = e.response.text if e.response is not None else str(e)
            return ImageGenerationResult(None, latency, req_info, f"HTTP Error: {e}\n{error_details}")

        except Exception as e:
            latency = time.time() - start_time
            logger.error(f"Error processing {image_path}: {e}")
            return ImageGenerationResult(None, latency, req_info, f"Exception: {e}")
