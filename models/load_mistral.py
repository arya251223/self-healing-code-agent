import requests
import json
from typing import Dict, Any, Optional
from utils.logger import get_logger

logger = get_logger(__name__)

class MistralClient:
    """Client for Mistral 7B Instruct model via Ollama"""
    
    def __init__(self, config: Dict[str, Any]):
        self.model = config.get('name', 'mistral:7b-instruct')
        self.host = config.get('host', 'http://localhost:11434')
        self.temperature = config.get('temperature', 0.1)
        self.max_tokens = config.get('max_tokens', 2048)
        self.timeout = config.get('timeout', 60)
        
    def generate(self, 
                 prompt: str, 
                 system: Optional[str] = None,
                 temperature: Optional[float] = None,
                 max_tokens: Optional[int] = None) -> str:
        """Generate completion from Mistral"""
        
        full_prompt = prompt
        if system:
            full_prompt = f"{system}\n\n{prompt}"
            
        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": temperature or self.temperature,
                "num_predict": max_tokens or self.max_tokens,
            }
        }
        
        try:
            logger.debug(f"Calling Mistral with prompt length: {len(full_prompt)}")
            response = requests.post(
                f"{self.host}/api/generate",
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            result = response.json()
            return result['response'].strip()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Mistral API error: {e}")
            raise RuntimeError(f"Failed to call Mistral: {e}")
    
    def generate_json(self, 
                      prompt: str, 
                      system: Optional[str] = None) -> Dict[str, Any]:
        """Generate JSON response from Mistral"""
        
        json_instruction = "\n\nYou must respond with valid JSON only. No markdown, no explanations."
        full_prompt = prompt + json_instruction
        
        response = self.generate(full_prompt, system, temperature=0.0)
        
        # Extract JSON from response
        try:
            # Try direct parsing
            return json.loads(response)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            import re
            json_match = re.search(r'```json\s*(\{.*?\})\s*```', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(1))
            
            # Try to find any JSON object
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
                
            logger.error(f"Failed to parse JSON from response: {response}")
            raise ValueError("Could not extract valid JSON from response")
    
    def create_mistral_client(config: Dict[str, Any]):
        """Create Mistral client with auto-fallback"""
    
        from models.auto_fallback import AutoFallbackClient
        from tests.run_demo import MockLLMClient
    
        return AutoFallbackClient(MistralClient, MockLLMClient, config)