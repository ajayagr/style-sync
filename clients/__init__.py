from .azure import AzureGenerator
from .stability import StabilityGenerator

def get_generator(provider_name):
    """
    Factory to get the appropriate image generator.
    """
    if provider_name.lower() == "azure":
        return AzureGenerator()
    elif provider_name.lower() == "stability":
        return StabilityGenerator()
    else:
        raise ValueError(f"Unknown provider: {provider_name}")
