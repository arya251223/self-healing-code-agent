import os
import yaml
from typing import Dict, Any
from dotenv import load_dotenv

def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """Load configuration from YAML file"""
    
    # Load environment variables
    load_dotenv()
    
    # Load YAML config
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    # Replace environment variables
    config = _replace_env_vars(config)
    
    # Add data directory
    config['data_dir'] = 'data'
    os.makedirs(config['data_dir'], exist_ok=True)
    
    return config

def _replace_env_vars(config: Any) -> Any:
    """Recursively replace ${VAR} with environment variables"""
    
    if isinstance(config, dict):
        return {k: _replace_env_vars(v) for k, v in config.items()}
    elif isinstance(config, list):
        return [_replace_env_vars(item) for item in config]
    elif isinstance(config, str) and config.startswith('${') and config.endswith('}'):
        var_name = config[2:-1]
        return os.getenv(var_name, config)
    else:
        return config