from typing import Dict, Any, List, Optional
from models.load_starcoder import StarCoderClient
from services.test_runner import TestRunner
from services.code_parser import CodeParser
from utils.logger import get_logger

logger = get_logger(__name__)

class TesterAgent:
    """Agent responsible for test generation and execution"""
    
    SYSTEM_PROMPT = """You are TesterAgent using StarCoder. Generate minimal pytest-style tests to validate the fix if tests are missing, and run tests using the sandbox. Return structured test_results JSON.

INSTRUCTIONS:
1. If existing tests exist, run them and return detailed stdout/stderr.
2. If none exist, generate 2-5 unit tests covering the bug scenario.
3. Tests should be deterministic and quick (no heavy external deps).
4. Use pytest style with assert statements.
5. Cover normal cases, edge cases, and the specific bug being fixed.
"""
    
    def __init__(self, starcoder_client: StarCoderClient, test_runner: TestRunner):
        self.client = starcoder_client
        self.test_runner = test_runner
        self.code_parser = CodeParser()
    
    def run_tests(self, 
                  patch: Dict[str, Any],
                  repo_path: str,
                  plan: Dict[str, Any]) -> Dict[str, Any]:
        """Run tests for patched code"""
        
        logger.info("Running tests for patched code")
        
        # Discover existing tests
        test_files = self.test_runner.discover_tests(repo_path)
        
        if not test_files:
            logger.info("No existing tests found, generating new tests")
            # Generate tests for the patched code
            test_code = self.generate_tests(patch, plan)
            test_files = [self._save_generated_tests(test_code, repo_path)]
        
        # Run tests
        results = self.test_runner.run(
            test_files=test_files,
            repo_path=repo_path,
            timeout=plan.get('timeout_secs', 30)
        )
        
        logger.info(f"Tests completed: {results['passed']}/{results['total']} passed")
        
        return results
    
    def generate_tests(self, 
                       patch: Dict[str, Any],
                       plan: Dict[str, Any]) -> str:
        """Generate test cases for the patch"""
        
        logger.info(f"Generating tests for {plan['target_function']}")
        
        # Extract function code from patch or plan
        function_code = self._extract_function_from_patch(patch, plan)
        
        try:
            test_code = self.client.generate_tests(
                function_code=function_code,
                function_name=plan.get('target_function', 'unknown'),
                system=self.SYSTEM_PROMPT
            )
            
            # Clean and validate test code
            test_code = self._clean_test_code(test_code)
            
            logger.info("Tests generated successfully")
            return test_code
            
        except Exception as e:
            logger.error(f"Test generation failed: {e}")
            # Return minimal template
            return self._create_minimal_test_template(plan)
    
    def _extract_function_from_patch(self, 
                                      patch: Dict[str, Any],
                                      plan: Dict[str, Any]) -> str:
        """Extract the function code being tested"""
        
        # This would need access to the actual file content
        # For now, return a placeholder
        # In real implementation, read from repo
        
        target_file = plan.get('target_file', '')
        target_function = plan.get('target_function', '')
        
        try:
            with open(target_file, 'r') as f:
                content = f.read()
            
            # Parse and extract function
            function_code = self.code_parser.extract_function(content, target_function)
            return function_code
            
        except Exception as e:
            logger.warning(f"Could not extract function: {e}")
            return f"# Function: {target_function}\n# (source not available)"
    
    def _clean_test_code(self, test_code: str) -> str:
        """Clean generated test code"""
        
        # Remove markdown code blocks
        import re
        test_code = re.sub(r'```python\n?', '', test_code)
        test_code = re.sub(r'```\n?', '', test_code)
        
        # Ensure imports
        if 'import pytest' not in test_code:
            test_code = 'import pytest\n\n' + test_code
        
        return test_code.strip()
    
    def _create_minimal_test_template(self, plan: Dict[str, Any]) -> str:
        """Create a minimal test template"""
        
        function_name = plan.get('target_function', 'target_function')
        
        return f"""import pytest

def test_{function_name}_basic():
    \"\"\"Basic test for {function_name}\"\"\"
    # TODO: Implement test
    pass

def test_{function_name}_edge_cases():
    \"\"\"Edge case tests for {function_name}\"\"\"
    # TODO: Implement test
    pass
"""
    
    def _save_generated_tests(self, test_code: str, repo_path: str) -> str:
        """Save generated tests to file"""
        
        import os
        
        test_dir = os.path.join(repo_path, 'tests')
        os.makedirs(test_dir, exist_ok=True)
        
        test_file = os.path.join(test_dir, 'test_generated.py')
        
        with open(test_file, 'w') as f:
            f.write(test_code)
        
        logger.info(f"Generated tests saved to {test_file}")
        return test_file