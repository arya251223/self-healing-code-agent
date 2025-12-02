"""
Auto-fallback to mock models when Ollama is unavailable
"""

import requests
from typing import Dict, Any
from utils.logger import get_logger

logger = get_logger(__name__)

class AutoFallbackClient:
    """Automatically fallback to mock when real model unavailable"""
    
    def __init__(self, real_client_class, mock_client_class, config: Dict[str, Any]):
        self.config = config
        self.real_client_class = real_client_class
        self.mock_client_class = mock_client_class
        
        # Try real client first
        self.use_mock = not self._test_ollama_connection()
        
        if self.use_mock:
            logger.warning(f"⚠️  Ollama not available, using MOCK mode")
            from tests.run_demo import MockLLMClient, MockCodeLlamaClient, MockStarCoderClient
            
            # Use mocks
            if 'mistral' in config.get('name', '').lower():
                self.client = MockLLMClient(config)
            elif 'codellama' in config.get('name', '').lower():
                self.client = MockCodeLlamaClient(config)
            elif 'starcoder' in config.get('name', '').lower():
                self.client = MockStarCoderClient(config)
            else:
                self.client = MockLLMClient(config)
        else:
            logger.info(f"✓ Using real Ollama model: {config.get('name')}")
            self.client = real_client_class(config)
    
    def _test_ollama_connection(self) -> bool:
        """Test if Ollama is running"""
        try:
            host = self.config.get('host', 'http://localhost:11434')
            response = requests.get(f"{host}/api/tags", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def __getattr__(self, name):
        """Delegate all methods to underlying client"""
        return getattr(self.client, name)