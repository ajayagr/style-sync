from abc import ABC, abstractmethod

class ImageGenerator(ABC):
    @abstractmethod
    def process_image(self, image_path, prompt, strength):
        """
        Process an image with the given prompt and strength.
        Returns: Binary image data bytes or None if failed.
        """
        pass
