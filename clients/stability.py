import logging
import os
import requests
from pathlib import Path
from .base import ImageGenerator

logger = logging.getLogger(__name__)

class StabilityGenerator(ImageGenerator):
    def process_image(self, image_path, prompt, strength):
        api_key = os.environ.get("STABILITY_API_KEY")
        if not api_key:
            raise ValueError("Environment variable STABILITY_API_KEY must be set.")
            
        url = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/image-to-image"

        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        
        influence = 1.0 - strength # Convert "change strength" to "retention strength"
        influence = max(0.01, min(0.99, influence)) # Clamp to safe range

        files = {
            "init_image": open(image_path, "rb")
        }
        
        data = {
            "image_strength": influence,
            "init_image_mode": "IMAGE_STRENGTH",
            "text_prompts[0][text]": prompt,
            "text_prompts[0][weight]": 1,
            "cfg_scale": 7,
            "samples": 1,
            "steps": 30,
        }

        try:
            response = requests.post(url, headers=headers, files=files, data=data)
            
            if response.status_code != 200:
                logger.error(f"Stability API Error: {response.text}")
                return None

            data = response.json()
            for image in data["artifacts"]:
                if image["finishReason"] == "CONTENT_FILTERED":
                    logger.warning("Stability AI: Content Filtered")
                    return None
                import base64
                return base64.b64decode(image["base64"])
                
        except requests.exceptions.RequestException as e:
            logger.error(f"API Error processing {image_path}: {e}")
            return None
            
        return None
