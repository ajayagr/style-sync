from abc import ABC, abstractmethod
from typing import Optional, Union
from pathlib import Path
from dataclasses import dataclass

@dataclass
class ImageGenerationResult:
    data: Optional[bytes]
    latency: float
    request_info: str
    response_info: str

class ImageGenerator(ABC):
    @abstractmethod
    def process_image(self, input_path: Path, prompt: str, strength: float) -> ImageGenerationResult:
        """
        Process an image using the provider's API.
        Returns ImageGenerationResult containing data and metrics.
        """
        pass
    
    def process_image_bytes(self, image_data: bytes, filename: str, prompt: str, strength: float) -> ImageGenerationResult:
        """
        Process image bytes directly (for serverless).
        Default implementation writes to temp file and calls process_image.
        Subclasses can override for direct byte handling.
        """
        import tempfile
        import os
        from pathlib import Path
        
        # Write to temp file
        suffix = Path(filename).suffix
        fd, tmp_path = tempfile.mkstemp(suffix=suffix)
        os.close(fd)
        
        try:
            with open(tmp_path, 'wb') as f:
                f.write(image_data)
            return self.process_image(Path(tmp_path), prompt, strength)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
