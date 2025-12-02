import ast
import re
from typing import Dict, Any, List, Optional
from utils.logger import get_logger

logger = get_logger(__name__)

class CodeParser:
    """Parse and extract information from code"""
    
    def extract_function(self, content: str, function_name: str) -> str:
        """Extract a specific function from code"""
        
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == function_name:
                    # Get the source code for this function
                    lines = content.split('\n')
                    start_line = node.lineno - 1
                    end_line = node.end_lineno if hasattr(node, 'end_lineno') else start_line + 1
                    
                    function_lines = lines[start_line:end_line]
                    return '\n'.join(function_lines)
            
            logger.warning(f"Function {function_name} not found")
            return f"# Function {function_name} not found"
        
        except SyntaxError as e:
            logger.error(f"Syntax error parsing code: {e}")
            return f"# Syntax error: {e}"
    
    def extract_class(self, content: str, class_name: str) -> str:
        """Extract a specific class from code"""
        
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == class_name:
                    lines = content.split('\n')
                    start_line = node.lineno - 1
                    end_line = node.end_lineno if hasattr(node, 'end_lineno') else start_line + 1
                    
                    class_lines = lines[start_line:end_line]
                    return '\n'.join(class_lines)
            
            logger.warning(f"Class {class_name} not found")
            return f"# Class {class_name} not found"
        
        except SyntaxError as e:
            logger.error(f"Syntax error parsing code: {e}")
            return f"# Syntax error: {e}"
    
    def parse_trace(self, trace: str) -> Dict[str, Any]:
        """Parse Python stack trace"""
        
        # Extract error type and message
        error_match = re.search(r'(\w+Error): (.+)$', trace, re.MULTILINE)
        error_type = error_match.group(1) if error_match else 'UnknownError'
        error_message = error_match.group(2) if error_match else ''
        
        # Extract file paths and line numbers
        file_pattern = r'File "([^"]+)", line (\d+)'
        matches = re.findall(file_pattern, trace)
        
        files = []
        file_lines = {}
        
        for file_path, line_num in matches:
            if file_path not in files:
                files.append(file_path)
            file_lines[file_path] = int(line_num)
        
        # Find the failed line (usually the last one in the trace)
        failed_file = files[-1] if files else None
        failed_line = file_lines.get(failed_file, 0) if failed_file else 0
        
        return {
            "error_type": error_type,
            "error_message": error_message,
            "files": files,
            "file_lines": file_lines,
            "failed_file": failed_file,
            "failed_line": failed_line
        }
    
    def get_imports(self, content: str) -> List[str]:
        """Extract all imports from code"""
        
        imports = []
        
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    module = node.module or ''
                    for alias in node.names:
                        imports.append(f"{module}.{alias.name}" if module else alias.name)
        
        except SyntaxError:
            pass
        
        return imports
    
    def get_function_calls(self, content: str) -> List[str]:
        """Extract all function calls from code"""
        
        calls = []
        
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    if isinstance(node.func, ast.Name):
                        calls.append(node.func.id)
                    elif isinstance(node.func, ast.Attribute):
                        calls.append(node.func.attr)
        
        except SyntaxError:
            pass
        
        return calls