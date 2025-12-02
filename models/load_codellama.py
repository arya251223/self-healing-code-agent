import requests
import json
from typing import Optional, Dict, Any
from utils.logger import get_logger

logger = get_logger(__name__)

class CodeLlamaClient:
    """Client for CodeLlama 7B model via Ollama"""
    
    def __init__(self, config: Dict[str, Any]):
        self.model = config.get('name', 'codellama:7b-instruct')
        self.host = config.get('host', 'http://localhost:11434')
        self.temperature = config.get('temperature', 0.2)
        self.max_tokens = config.get('max_tokens', 4096)
        self.timeout = config.get('timeout', 90)
        
    def generate_patch(self, 
                       code_context: str,
                       plan: Dict[str, Any],
                       system: Optional[str] = None,
                       temperature: Optional[float] = None) -> str:
        """Generate code patch using CodeLlama"""
        
        prompt = self._build_patch_prompt(code_context, plan)
        
        full_prompt = prompt
        if system:
            full_prompt = f"{system}\n\n{prompt}"
            
        payload = {
            "model": self.model,
            "prompt": full_prompt,
            "stream": False,
            "options": {
                "temperature": temperature or self.temperature,
                "num_predict": self.max_tokens,
            }
        }
        
        try:
            logger.debug(f"Generating patch with CodeLlama")
            response = requests.post(
                f"{self.host}/api/generate",
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            result = response.json()
            return result['response'].strip()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"CodeLlama API error: {e}")
            raise RuntimeError(f"Failed to call CodeLlama: {e}")
    
    def _build_patch_prompt(self, code_context: str, plan: Dict[str, Any]) -> str:
        """Build prompt for patch generation"""
        return f"""Given the following code and repair plan, generate a minimal unified diff patch.

CODE:
REPAIR PLAN:
Strategy: {plan.get('strategy', 'unknown')}
Target: {plan.get('target_function', 'unknown')}
Issue: {plan.get('issue_description', 'unknown')}

REQUIREMENTS:

Generate ONLY the minimal changes needed
Use unified diff format (--- +++ @@ format)
Ensure code is syntactically correct
Do not add unnecessary refactoring
Preserve existing code style
Generate the patch now:
"""