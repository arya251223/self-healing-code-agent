import os
import shutil
import subprocess
import tempfile
import ast
from typing import Dict, Any, Optional,List
from datetime import datetime
from utils.logger import get_logger

logger = get_logger(__name__)

class PatchApplier:
    """Apply and manage code patches"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.backup_dir = os.path.join(config.get('data_dir', 'data'), 'patches')
        os.makedirs(self.backup_dir, exist_ok=True)
        
        self.current_backup = None
    
    def dry_apply(self, patch: str, target_file: str) -> Dict[str, Any]:
        """Validate patch without applying it"""
        
        logger.info(f"Dry-run applying patch to {target_file}")
        
        try:
            # Read current file
            with open(target_file, 'r') as f:
                original_content = f.read()
            
            # Apply patch to get new content
            new_content = self._apply_patch_to_string(original_content, patch)
            
            # Validate syntax
            try:
                ast.parse(new_content)
                
                return {
                    "success": True,
                    "new_content": new_content,
                    "message": "Patch is valid"
                }
            
            except SyntaxError as e:
                logger.warning(f"Patched code has syntax error: {e}")
                return {
                    "success": False,
                    "error": f"Syntax error: {e.msg} at line {e.lineno}",
                    "new_content": new_content
                }
        
        except Exception as e:
            logger.error(f"Dry-run failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def apply(self, patch: str, target_file: str) -> Dict[str, Any]:
        """Apply patch to file"""
        
        logger.info(f"Applying patch to {target_file}")
        
        # Create backup first
        backup_path = self._create_backup(target_file)
        
        try:
            # Read current file
            with open(target_file, 'r') as f:
                original_content = f.read()
            
            # Apply patch
            new_content = self._apply_patch_to_string(original_content, patch)
            
            # Write new content
            with open(target_file, 'w') as f:
                f.write(new_content)
            
            logger.info(f"Patch applied successfully to {target_file}")
            
            self.current_backup = backup_path
            
            return {
                "success": True,
                "backup_path": backup_path,
                "message": "Patch applied"
            }
        
        except Exception as e:
            logger.error(f"Failed to apply patch: {e}")
            # Restore from backup
            self._restore_backup(backup_path, target_file)
            raise RuntimeError(f"Failed to apply patch: {e}")
    
    def rollback(self) -> Dict[str, Any]:
        """Rollback to previous backup"""
        
        if not self.current_backup:
            logger.warning("No backup to rollback to")
            return {"success": False, "message": "No backup available"}
        
        try:
            # Extract target file from backup metadata
            backup_info = self._get_backup_info(self.current_backup)
            target_file = backup_info['original_file']
            
            self._restore_backup(self.current_backup, target_file)
            
            logger.info(f"Rolled back to backup: {self.current_backup}")
            
            self.current_backup = None
            
            return {
                "success": True,
                "message": "Rollback successful"
            }
        
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def commit(self, message: str, run_id: str) -> Dict[str, Any]:
        """Commit changes to git"""
    
        logger.info(f"Committing changes: {message}")
    
        try:
        # Git add
            result = subprocess.run(['git', 'add', '-A'], 
                                capture_output=True, 
                                text=True, 
                                shell=True)  # Add shell=True for Windows
        
            if result.returncode != 0:
                logger.warning(f"Git add warning: {result.stderr}")
        
        # Git commit
            full_message = f"{message}\n\nSelf-healing run: {run_id}"
            result = subprocess.run(
                ['git', 'commit', '-m', full_message],
                capture_output=True,
                text=True,
                shell=True  # Add shell=True for Windows
            )
        
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                logger.error(f"Git commit failed: {error_msg}")
                return {
                    "success": False,
                    "error": error_msg
                }
        
        # Get commit hash
            result = subprocess.run(
                ['git', 'rev-parse', 'HEAD'],
                capture_output=True,
                text=True,
                check=True,
                shell=True  # Add shell=True for Windows
            )
            commit_hash = result.stdout.strip()
        
            logger.info(f"Committed as {commit_hash}")
        
            self.current_backup = None  # Clear backup after successful commit
        
            return {
                "success": True,
                "commit_hash": commit_hash,
                "message": message
            }
    
        except subprocess.CalledProcessError as e:
            logger.error(f"Git commit failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
        except Exception as e:
            logger.error(f"Git commit exception: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _apply_patch_to_string(self, original: str, patch: str) -> str:
        """Apply unified diff patch to string content"""
        
        import re
        
        original_lines = original.split('\n')
        result_lines = list(original_lines)
        
        # Parse hunks from patch
        hunks = self._parse_patch_hunks(patch)
        
        # Apply each hunk
        offset = 0  # Track line number offset from previous hunks
        
        for hunk in hunks:
            start_line = hunk['start_line'] - 1 + offset
            
            # Remove deleted lines
            for i, change in enumerate(hunk['changes']):
                if change['type'] == 'remove':
                    del result_lines[start_line]
                    offset -= 1
                elif change['type'] == 'add':
                    result_lines.insert(start_line, change['line'])
                    start_line += 1
                    offset += 1
                else:  # context
                    start_line += 1
        
        return '\n'.join(result_lines)
    
    def _parse_patch_hunks(self, patch: str) -> List[Dict[str, Any]]:
        """Parse unified diff into hunks"""
        
        import re
        
        hunks = []
        current_hunk = None
        
        for line in patch.split('\n'):
            # Hunk header
            hunk_match = re.match(r'@@ -(\d+),?\d* \+(\d+),?\d* @@', line)
            if hunk_match:
                if current_hunk:
                    hunks.append(current_hunk)
                
                current_hunk = {
                    'start_line': int(hunk_match.group(2)),
                    'changes': []
                }
                continue
            
            if current_hunk is not None:
                if line.startswith('+') and not line.startswith('+++'):
                    current_hunk['changes'].append({
                        'type': 'add',
                        'line': line[1:]
                    })
                elif line.startswith('-') and not line.startswith('---'):
                    current_hunk['changes'].append({
                        'type': 'remove',
                        'line': line[1:]
                    })
                elif line.startswith(' '):
                    current_hunk['changes'].append({
                        'type': 'context',
                        'line': line[1:]
                    })
        
        if current_hunk:
            hunks.append(current_hunk)
        
        return hunks
    
    def _create_backup(self, file_path: str) -> str:
        """Create backup of file"""
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_name = f"{os.path.basename(file_path)}_{timestamp}.backup"
        backup_path = os.path.join(self.backup_dir, backup_name)
        
        shutil.copy2(file_path, backup_path)
        
        # Save metadata
        metadata_path = backup_path + '.meta'
        with open(metadata_path, 'w') as f:
            import json
            json.dump({
                'original_file': file_path,
                'timestamp': timestamp,
                'backup_path': backup_path
            }, f)
        
        logger.debug(f"Created backup: {backup_path}")
        
        return backup_path
    
    def _restore_backup(self, backup_path: str, target_file: str):
        """Restore file from backup"""
        
        shutil.copy2(backup_path, target_file)
        logger.info(f"Restored {target_file} from backup")
    
    def _get_backup_info(self, backup_path: str) -> Dict[str, Any]:
        """Get backup metadata"""
        
        metadata_path = backup_path + '.meta'
        
        with open(metadata_path, 'r') as f:
            import json
            return json.load(f)