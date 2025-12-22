import yaml
from pathlib import Path

def load_config(config_path="config.yaml"):
    """
    Loads configuration from a YAML file.
    """
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Configuration file {config_path} not found.")
    
    with open(path, "r") as f:
        config = yaml.safe_load(f)
    
    return config
