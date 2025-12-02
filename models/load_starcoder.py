
### `models/load_starcoder.py`
import requests
from typing import List, Dict, Any, Optional
from utils.logger import get_logger

logger = get_logger(__name__)

class StarCoderClient:
    """Client for StarCoder 7B model via Ollama"""
    
    def __init__(self, config: Dict[str, Any]):
        self.model = config.get('name', 'starcoder:7b')
        self.host = config.get('host', 'http://localhost:11434')
        self.temperature = config.get('temperature', 0.1)
        self.max_tokens = config.get('max_tokens', 2048)
        self.timeout = config.get('timeout', 60)
        
    def generate_tests(self, 
                       function_code: str,
                       function_name: str,
                       system: Optional[str] = None) -> str:
        """Generate test cases using StarCoder"""
        
        prompt = self._build_test_prompt(function_code, function_name)
        
        full_prompt = prompt
        if system:
            full_prompt = f"{system}\n\n{prompt}"
            
        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            }
        }
        
        try:
            logger.debug(f"Generating tests with StarCoder for {function_name}")
            response = requests.post(
                f"{self.host}/api/generate",
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            result = response.json()
            return result['response'].strip()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"StarCoder API error: {e}")
            raise RuntimeError(f"Failed to call StarCoder: {e}")
    
    def _build_test_prompt(self, function_code: str, function_name: str) -> str:
        """Build prompt for test generation"""
        return f"""Generate pytest unit tests for the following Python function.

FUNCTION:
REQUIREMENTS:

Generate 3-5 test cases covering normal and edge cases
Use pytest style (test_* functions)
Include assertions for expected behavior
Test error conditions if applicable
Make tests deterministic (no random values)
Generate the test code now:


import pytest

"""