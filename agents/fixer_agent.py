import re
from typing import Dict, Any, Optional
from models.load_codellama import CodeLlamaClient
from services.code_parser import CodeParser
from utils.logger import get_logger

logger = get_logger(__name__)

class FixerAgent:
    """Agent responsible for generating code patches"""
    
    SYSTEM_PROMPT = """You are FixerAgent using CodeLlama. Given a small code context and a plan, produce a minimal unified-diff patch that fixes the described bug.

INSTRUCTIONS:
1. Only change what is necessary.
2. Prefer explicit fixes (e.g., add guard clauses, correct operator).
3. Return a unified-diff; include contextual lines.
4. Ensure generated code is syntactically correct Python.
5. Do not add unrelated refactors.
6. Use this exact format:

--- a/path/to/file.py
+++ b/path/to/file.py
@@ -line_start,count +line_start,count @@
 context line
-removed line
+added line
 context line
"""
    
    def __init__(self, codellama_client: CodeLlamaClient):
        self.client = codellama_client
        self.code_parser = CodeParser()
    
    def generate_patch(self, 
                       file_path: str,
                       file_content: str,
                       plan: Dict[str, Any],
                       bug_report: Dict[str, Any]) -> Dict[str, Any]:
        """Generate a patch based on the plan"""
        
        logger.info(f"Generating patch for {file_path} using {plan['strategy']}")
        
        # Extract relevant code section
        code_context = self._extract_code_context(file_content, plan)
        
        # Generate patch
        try:
            patch_text = self.client.generate_patch(
                code_context=code_context,
                plan=plan,
                system=self.SYSTEM_PROMPT
            )
            
            # Clean and validate patch
            patch_text = self._clean_patch(patch_text, file_path)
            
            # Minimize patch (remove unnecessary context)
            patch_text = self._minimize_patch(patch_text)
            
            # Extract metadata
            metadata = self._extract_patch_metadata(patch_text)
            
            logger.info(f"Patch generated: {metadata['lines_changed']} lines changed")
            
            return {
                "patch": patch_text,
                "metadata": metadata,
                "strategy": plan['strategy'],
                "confidence": plan.get('confidence', 0.5)
            }
            
        except Exception as e:
            logger.error(f"Patch generation failed: {e}")
            raise RuntimeError(f"Failed to generate patch: {e}")
    
    def _extract_code_context(self, file_content: str, plan: Dict[str, Any]) -> str:
        """Extract relevant code section with context"""
        
        lines = file_content.split('\n')
        start_line = max(0, plan.get('line_range', [0, 0])[0] - 5)  # 5 lines before
        end_line = min(len(lines), plan.get('line_range', [0, len(lines)])[1] + 5)  # 5 lines after
        
        context_lines = lines[start_line:end_line]
        
        # Add line numbers for reference
        numbered_context = "\n".join([
            f"{start_line + i + 1:4d} | {line}"
            for i, line in enumerate(context_lines)
        ])
        
        return numbered_context
    
    def _clean_patch(self, patch_text: str, file_path: str) -> str:
        """Clean patch text and ensure proper format"""
        
        # Remove markdown code blocks if present
        patch_text = re.sub(r'```diff\n', '', patch_text)
        patch_text = re.sub(r'```\n?', '', patch_text)
        
        # Ensure proper header
        if not patch_text.startswith('---'):
            header = f"--- a/{file_path}\n+++ b/{file_path}\n"
            # Find the @@ line
            hunk_match = re.search(r'^@@.*@@', patch_text, re.MULTILINE)
            if hunk_match:
                patch_text = header + patch_text
            else:
                # No proper hunk header, might need to add it
                pass
        
        return patch_text.strip()
    
    def _minimize_patch(self, patch_text: str) -> str:
        """Remove unnecessary context lines from patch"""
        
        lines = patch_text.split('\n')
        minimized = []
        
        in_hunk = False
        context_buffer = []
        max_context = 3  # Keep max 3 context lines around changes
        
        for line in lines:
            if line.startswith('---') or line.startswith('+++'):
                minimized.append(line)
            elif line.startswith('@@'):
                in_hunk = True
                minimized.append(line)
                context_buffer = []
            elif in_hunk:
                if line.startswith('-') or line.startswith('+'):
                    # Add buffered context before change
                    minimized.extend(context_buffer[-max_context:])
                    context_buffer = []
                    minimized.append(line)
                elif line.startswith(' '):
                    # Context line
                    context_buffer.append(line)
                else:
                    # End of hunk
                    minimized.extend(context_buffer[:max_context])
                    context_buffer = []
                    in_hunk = False
        
        return '\n'.join(minimized)
    
    def _extract_patch_metadata(self, patch_text: str) -> Dict[str, Any]:
        """Extract metadata from patch"""
        
        lines = patch_text.split('\n')
        
        additions = sum(1 for line in lines if line.startswith('+') and not line.startswith('+++'))
        deletions = sum(1 for line in lines if line.startswith('-') and not line.startswith('---'))
        
        # Extract changed line ranges
        hunks = re.findall(r'@@ -(\d+),?\d* \+(\d+),?\d* @@', patch_text)
        
        return {
            "lines_added": additions,
            "lines_removed": deletions,
            "lines_changed": additions + deletions,
            "hunks": len(hunks),
            "affected_lines": hunks
        }