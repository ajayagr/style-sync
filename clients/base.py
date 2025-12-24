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
