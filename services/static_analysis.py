import ast
import subprocess
from typing import List, Dict, Any
from utils.logger import get_logger

logger = get_logger(__name__)

class StaticAnalyzer:
    """Static code analysis using AST and linters"""
    
    def __init__(self):
        self.severity_map = {
            'E': 'HIGH',      # Error
            'W': 'MEDIUM',    # Warning
            'C': 'LOW',       # Convention
            'R': 'LOW',       # Refactor
            'F': 'HIGH'       # Fatal
        }
    
    def analyze(self, file_path: str, content: str) -> List[Dict[str, Any]]:
        """Analyze code for issues"""
        
        issues = []
        
        # AST-based analysis
        issues.extend(self._ast_analysis(content, file_path))
        
        # Flake8 analysis
        issues.extend(self._flake8_analysis(file_path))
        
        # Pylint analysis (optional, can be slow)
        # issues.extend(self._pylint_analysis(file_path))
        
        return issues
    
    def _ast_analysis(self, content: str, file_path: str) -> List[Dict[str, Any]]:
        """AST-based syntax and structural analysis"""
        
        issues = []
        
        try:
            tree = ast.parse(content, filename=file_path)
            
            # Check for common issues
            for node in ast.walk(tree):
                # Detect bare except
                if isinstance(node, ast.ExceptHandler):
                    if node.type is None:
                        issues.append({
                            "file": file_path,
                            "line": node.lineno,
                            "severity": "MEDIUM",
                            "message": "Bare except clause (catches all exceptions)",
                            "type": "ast"
                        })
                
                # Detect unused variables (simple check)
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id.startswith('_'):
                            # Likely intentionally unused
                            pass
                
                # Detect dangerous default arguments
                if isinstance(node, ast.FunctionDef):
                    for default in node.args.defaults:
                        if isinstance(default, (ast.List, ast.Dict, ast.Set)):
                            issues.append({
                                "file": file_path,
                                "line": node.lineno,
                                "severity": "HIGH",
                                "message": f"Dangerous default argument in function {node.name}",
                                "type": "ast"
                            })
        
        except SyntaxError as e:
            issues.append({
                "file": file_path,
                "line": e.lineno or 0,
                "severity": "HIGH",
                "message": f"Syntax error: {e.msg}",
                "type": "syntax"
            })
        
        return issues
    
    def _flake8_analysis(self, file_path: str) -> List[Dict[str, Any]]:
        """Run flake8 linter"""
    
        issues = []
    
        try:
            result = subprocess.run(
                ['flake8', '--format=%(path)s:%(row)d:%(col)d: %(code)s %(text)s', file_path],
                capture_output=True,
                text=True,
                timeout=10
            )
        
            for line in result.stdout.strip().split('\n'):
                if line:
                # Fix: Handle Windows paths with drive letters (E:\path)
                # Split on first colon after drive letter
                    parts = line.split(':', 4)  # Changed from 3 to 4
                
                # Handle both Unix and Windows paths
                    if len(parts) >= 4:
                        try:
                        # For Windows: E:\path\file.py:10:5: E501 message
                        # parts = ['E', '\path\file.py', '10', '5', 'E501 message']
                        # So we need to reconstruct the path
                        
                            if len(parts[0]) == 1:  # Windows drive letter
                                file_part = parts[0] + ':' + parts[1]
                                line_num = int(parts[2])
                                col_num = int(parts[3]) if len(parts) > 3 else 0
                                msg_part = parts[4] if len(parts) > 4 else ''
                            else:  # Unix path
                                file_part = parts[0]
                                line_num = int(parts[1])
                                col_num = int(parts[2]) if len(parts) > 2 else 0
                                msg_part = parts[3] if len(parts) > 3 else ''
                        
                            issues.append({
                                "file": file_part,
                                "line": line_num,
                                "severity": self.severity_map.get(msg_part.strip()[0] if msg_part else 'C', 'LOW'),
                                "message": msg_part.strip(),
                                "type": "flake8"
                            })
                        except (ValueError, IndexError) as e:
                        # Skip malformed lines
                            logger.debug(f"Could not parse flake8 line: {line} - {e}")
                            continue
    
        except (subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.warning(f"Flake8 analysis failed: {e}")
    
        return issues
    
    def _pylint_analysis(self, file_path: str) -> List[Dict[str, Any]]:
        """Run pylint linter"""
        
        issues = []
        
        try:
            result = subprocess.run(
                ['pylint', '--output-format=json', file_path],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            import json
            pylint_results = json.loads(result.stdout)
            
            for item in pylint_results:
                issues.append({
                    "file": file_path,
                    "line": item.get('line', 0),
                    "severity": self.severity_map.get(item.get('type', 'I')[0], 'LOW'),
                    "message": item.get('message', ''),
                    "type": "pylint"
                })
        
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Pylint analysis failed: {e}")
        
        return issues