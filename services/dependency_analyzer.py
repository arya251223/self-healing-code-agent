import os
import ast
import json
from typing import Dict, Any, List, Set, Optional
from collections import defaultdict
from utils.logger import get_logger

logger = get_logger(__name__)

class DependencyAnalyzer:
    """Analyze code dependencies and relationships"""
    
    def __init__(self):
        self.dependency_cache = {}
    
    def build_dependency_graph(self, files: List[str]) -> Dict[str, List[str]]:
        """Build dependency graph for given files"""
    
        logger.info(f"Building dependency graph for {len(files)} files")
    
        graph = defaultdict(list)
    
        for file_path in files:
            if not os.path.exists(file_path):
                continue
        
            try:
            # Try UTF-8 first, then fallback to other encodings
                content = None
                for encoding in ['utf-8', 'latin-1', 'cp1252']:
                    try:
                        with open(file_path, 'r', encoding=encoding) as f:
                            content = f.read()
                        break
                    except UnicodeDecodeError:
                        continue
            
                if content is None:
                    logger.warning(f"Could not decode {file_path}")
                    continue
            
            # Get imports
                imports = self._extract_imports(content)
            
            # Map imports to files in the project
                for imp in imports:
                    dependent_file = self._resolve_import_to_file(imp, file_path)
                    if dependent_file and dependent_file in files:
                        graph[file_path].append(dependent_file)
        
            except Exception as e:
                logger.warning(f"Could not analyze {file_path}: {e}")
    
        return dict(graph)
    
    def get_affected_files(self, changed_file: str, repo_path: str) -> List[str]:
        """Get all files that might be affected by changes to a file"""
        
        logger.info(f"Finding files affected by {changed_file}")
        
        affected = set()
        affected.add(changed_file)
        
        # Find all Python files in repo
        all_files = self._find_python_files(repo_path)
        
        # Build reverse dependency graph
        reverse_deps = defaultdict(list)
        
        for file_path in all_files:
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                
                imports = self._extract_imports(content)
                
                for imp in imports:
                    resolved = self._resolve_import_to_file(imp, file_path)
                    if resolved:
                        reverse_deps[resolved].append(file_path)
            
            except Exception as e:
                logger.warning(f"Could not analyze {file_path}: {e}")
        
        # BFS to find all affected files
        queue = [changed_file]
        visited = set()
        
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            
            visited.add(current)
            affected.add(current)
            
            # Add files that depend on current
            for dependent in reverse_deps.get(current, []):
                if dependent not in visited:
                    queue.append(dependent)
        
        logger.info(f"Found {len(affected)} affected files")
        
        return list(affected)
    
    def detect_project_type(self, repo_path: str) -> str:
        """Detect project type"""
        
        # Check for common project files
        if os.path.exists(os.path.join(repo_path, 'setup.py')):
            return 'python_package'
        elif os.path.exists(os.path.join(repo_path, 'pyproject.toml')):
            return 'python_modern'
        elif os.path.exists(os.path.join(repo_path, 'requirements.txt')):
            return 'python_simple'
        elif os.path.exists(os.path.join(repo_path, 'manage.py')):
            return 'django'
        elif os.path.exists(os.path.join(repo_path, 'app.py')) or os.path.exists(os.path.join(repo_path, 'wsgi.py')):
            return 'flask'
        else:
            return 'python_generic'
    
    def detect_test_framework(self, repo_path: str) -> str:
        """Detect test framework used"""
        
        # Check for test files
        test_files = []
        for root, dirs, files in os.walk(repo_path):
            for file in files:
                if file.startswith('test_') or file.endswith('_test.py'):
                    test_files.append(os.path.join(root, file))
        
        if not test_files:
            return 'none'
        
        # Check imports in test files
        for test_file in test_files[:5]:  # Check first 5
            try:
                with open(test_file, 'r') as f:
                    content = f.read()
                
                if 'import pytest' in content or 'from pytest' in content:
                    return 'pytest'
                elif 'import unittest' in content or 'from unittest' in content:
                    return 'unittest'
            except:
                pass
        
        return 'pytest'  # Default
    
    def get_dependencies(self, repo_path: str) -> List[str]:
        """Get project dependencies"""
        
        dependencies = []
        
        # Check requirements.txt
        req_file = os.path.join(repo_path, 'requirements.txt')
        if os.path.exists(req_file):
            with open(req_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Extract package name (before ==, >=, etc.)
                        pkg = line.split('==')[0].split('>=')[0].split('<=')[0].strip()
                        dependencies.append(pkg)
        
        # Check pyproject.toml
        pyproject_file = os.path.join(repo_path, 'pyproject.toml')
        if os.path.exists(pyproject_file):
            try:
                import toml
                with open(pyproject_file, 'r') as f:
                    data = toml.load(f)
                
                # Poetry
                if 'tool' in data and 'poetry' in data['tool']:
                    deps = data['tool']['poetry'].get('dependencies', {})
                    dependencies.extend([k for k in deps.keys() if k != 'python'])
            except:
                pass
        
        return dependencies
    
    def parse_trace_files(self, trace: str, repo_path: str) -> Dict[str, str]:
        """Parse stack trace and load relevant files"""
        
        import re
        
        files = {}
        
        # Extract file paths from trace
        file_pattern = r'File "([^"]+)", line (\d+)'
        matches = re.findall(file_pattern, trace)
        
        for file_path, line_num in matches:
            # Normalize path
            if not os.path.isabs(file_path):
                file_path = os.path.join(repo_path, file_path)
            
            if os.path.exists(file_path) and file_path not in files:
                try:
                    with open(file_path, 'r') as f:
                        files[file_path] = f.read()
                except Exception as e:
                    logger.warning(f"Could not read {file_path}: {e}")
        
        return files
    
    def _extract_imports(self, content: str) -> List[str]:
        """Extract all imports from code"""
        
        imports = []
        
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)
        
        except SyntaxError:
            # Fallback to regex
            import re
            import_pattern = r'^(?:from|import)\s+([\w.]+)'
            for match in re.finditer(import_pattern, content, re.MULTILINE):
                imports.append(match.group(1))
        
        return imports
    
    def _resolve_import_to_file(self, import_name: str, current_file: str) -> Optional[str]:
        """Try to resolve an import to a file path"""
        
        # Get directory of current file
        current_dir = os.path.dirname(current_file)
        
        # Convert import to file path
        # e.g., "mypackage.module" -> "mypackage/module.py"
        relative_path = import_name.replace('.', os.sep) + '.py'
        
        # Try relative to current file
        candidate = os.path.join(current_dir, relative_path)
        if os.path.exists(candidate):
            return candidate
        
        # Try as package
        candidate = os.path.join(current_dir, import_name.replace('.', os.sep), '__init__.py')
        if os.path.exists(candidate):
            return candidate
        
        # Could not resolve (might be external package)
        return None
    
    def _find_python_files(self, repo_path: str) -> List[str]:
        """Find all Python files in repository"""
        
        python_files = []
        
        for root, dirs, files in os.walk(repo_path):
            # Skip common ignore directories
            dirs[:] = [d for d in dirs if d not in ['.git', 'venv', 'env', '__pycache__', 'node_modules', '.pytest_cache']]
            
            for file in files:
                if file.endswith('.py'):
                    python_files.append(os.path.join(root, file))
        
        return python_files