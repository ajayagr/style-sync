__version__ = "1.0.0"
from .clients import get_generator

# Expose key components at package level
__all__ = ["get_generator"]
