"""
Automatic Git Integration for Self-Healing
Monitors repository, auto-scans, auto-fixes, and auto-pushes based on risk
"""

import os
import time
import threading
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from git import Repo, InvalidGitRepositoryError
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from utils.logger import get_logger

logger = get_logger(__name__)

class GitAutoHealer:
    """Automatic Git integration with risk-based auto-push"""
    
    def __init__(self, pipeline, config: Dict[str, Any], repo_path: str = "."):
        self.pipeline = pipeline
        self.config = config
        self.repo_path = repo_path
    
    # Auto-push settings
        self.auto_push_enabled = config.get('git_auto', {}).get('enabled', True)
        self.low_risk_timeout = config.get('git_auto', {}).get('low_risk_timeout', 30)
        self.require_approval_risks = config.get('git_auto', {}).get('require_approval_risks', ['MEDIUM', 'HIGH'])
    
    # Initialize git repo
        try:
            self.repo = Repo(repo_path)
            logger.info(f"✓ Git repository found: {repo_path}")
        except InvalidGitRepositoryError:
            logger.warning(f"⚠️  Not a git repository: {repo_path}")
            logger.warning("Auto-healing will work, but git push/commit features disabled")
            logger.warning("Run: python setup_git_repo.py to initialize git")
            self.repo = None
    
    # Pending approvals
        self.pending_approvals = {}
        self.approval_timers = {}
    
    # File watcher
        self.observer = None
        self.is_running = False
    
    def start_auto_healing(self):
        """Start automatic healing on file changes"""
        
        if not self.auto_push_enabled:
            logger.info("Auto-healing disabled in config")
            return
        
        logger.info("🚀 Starting automatic git healing...")
        
        # Start file watcher
        self.observer = Observer()
        handler = GitChangeHandler(self)
        self.observer.schedule(handler, self.repo_path, recursive=True)
        self.observer.start()
        
        self.is_running = True
        logger.info("✓ Auto-healing active - watching for changes")
    
    def stop_auto_healing(self):
        """Stop automatic healing"""
        
        if self.observer:
            self.observer.stop()
            self.observer.join()
        
        self.is_running = False
        logger.info("Auto-healing stopped")
    
    def on_file_changed(self, file_path: str):
        """Handle file change event"""
        
        # Skip non-Python files
        if not file_path.endswith('.py'):
            return
        
        # Skip generated/test files
        skip_patterns = ['__pycache__', '.pyc', 'venv', 'env', '.git']
        if any(pattern in file_path for pattern in skip_patterns):
            return
        
        logger.info(f"📝 File changed: {file_path}")
        
        # Trigger healing
        self.auto_heal_file(file_path)
    
    def auto_heal_file(self, file_path: str):
        """Automatically heal a file"""
        
        logger.info(f"🔍 Auto-scanning {file_path}...")
        
        try:
            # Run healing
            result = self.pipeline.heal(
                target_file=file_path,
                repo_path=self.repo_path,
                ci_context={'auto': True, 'trigger': 'file_change'}
            )
            
            # Handle result based on risk
            self.handle_healing_result(result, file_path)
            
        except Exception as e:
            logger.error(f"Auto-healing failed for {file_path}: {e}")
    
    def handle_healing_result(self, result: Dict[str, Any], file_path: str):
        """Handle healing result with risk-based auto-push"""
        
        status = result.get('status')
        details = result.get('details', {})
        
        if status != 'SUCCESS':
            logger.warning(f"Healing unsuccessful: {status}")
            return
        
        # Get risk level
        evaluation = details.get('evaluation', {})
        risk_level = self._determine_risk_level(details)
        
        logger.info(f"✓ Patch generated for {file_path} (Risk: {risk_level})")
        
        # Risk-based decision
        if risk_level == 'LOW':
            self._handle_low_risk_push(result, file_path)
        elif risk_level in ['MEDIUM', 'HIGH']:
            self._handle_high_risk_push(result, file_path, risk_level)
    
    def _handle_low_risk_push(self, result: Dict[str, Any], file_path: str):
        """Handle low-risk patches with timed auto-push"""
        
        run_id = result.get('run_id')
        
        logger.info(f"⏱️  LOW RISK: Auto-push in {self.low_risk_timeout}s (or approve manually)")
        
        # Send notification
        self.pipeline.notification_service.send_approval_request({
            'run_id': run_id,
            'file': file_path,
            'risk': 'LOW',
            'auto_push_in': self.low_risk_timeout,
            'details': result
        })
        
        # Store pending approval
        self.pending_approvals[run_id] = {
            'result': result,
            'file': file_path,
            'risk': 'LOW',
            'timestamp': datetime.now()
        }
        
        # Start countdown timer
        timer = threading.Timer(
            self.low_risk_timeout,
            self._auto_push_after_timeout,
            args=[run_id]
        )
        timer.start()
        self.approval_timers[run_id] = timer
        
        logger.info(f"⏲️  Timer started for {run_id}")
    
    def _handle_high_risk_push(self, result: Dict[str, Any], file_path: str, risk_level: str):
        """Handle medium/high-risk patches - require manual approval"""
        
        run_id = result.get('run_id')
        
        logger.warning(f"⚠️  {risk_level} RISK: Manual approval REQUIRED")
        
        # Send notification
        self.pipeline.notification_service.send_approval_request({
            'run_id': run_id,
            'file': file_path,
            'risk': risk_level,
            'requires_manual_approval': True,
            'details': result
        })
        
        # Store pending approval (no timer)
        self.pending_approvals[run_id] = {
            'result': result,
            'file': file_path,
            'risk': risk_level,
            'timestamp': datetime.now(),
            'requires_manual': True
        }
        
        logger.info(f"🔒 Waiting for manual approval for {run_id}")
    
    def _auto_push_after_timeout(self, run_id: str):
        """Auto-push after timeout if not manually approved/rejected"""
        
        if run_id not in self.pending_approvals:
            logger.warning(f"Run {run_id} not found in pending approvals")
            return
        
        approval = self.pending_approvals[run_id]
        
        logger.info(f"⏰ Timeout reached for {run_id} - AUTO-PUSHING")
        
        # Push the changes
        self.approve_and_push(run_id, auto=True)
    
    def approve_and_push(self, run_id: str, approved: bool = True, auto: bool = False):
        """Approve and push changes to git"""
        
        if run_id not in self.pending_approvals:
            logger.error(f"Run {run_id} not found")
            return {'success': False, 'error': 'Run not found'}
        
        approval = self.pending_approvals[run_id]
        
        # Cancel timer if exists
        if run_id in self.approval_timers:
            self.approval_timers[run_id].cancel()
            del self.approval_timers[run_id]
        
        if not approved:
            logger.info(f"❌ Patch rejected for {run_id}")
            # Rollback
            self.pipeline.manager.patch_applier.rollback()
            del self.pending_approvals[run_id]
            return {'success': True, 'action': 'rejected'}
        
        # Approved - commit and push
        result = approval['result']
        file_path = approval['file']
        
        logger.info(f"✅ Patch approved for {run_id} ({'AUTO' if auto else 'MANUAL'})")
        
        try:
            # Commit changes
            commit_msg = f"🤖 Auto-fix: {file_path}\n\nRun: {run_id}\nRisk: {approval['risk']}\nApproval: {'Auto' if auto else 'Manual'}"
            
            commit_result = self.pipeline.manager.patch_applier.commit(
                message=commit_msg,
                run_id=run_id
            )
            
            if commit_result.get('success'):
                logger.info(f"✓ Committed: {commit_result.get('commit_hash', 'unknown')[:8]}")
                
                # Push to remote
                if self.repo:
                    push_result = self._push_to_remote()
                    
                    if push_result['success']:
                        logger.info(f"🚀 Pushed to remote successfully!")
                        
                        # Send success notification
                        self.pipeline.notification_service.send_success_notification({
                            'run_id': run_id,
                            'file': file_path,
                            'commit': commit_result.get('commit_hash'),
                            'auto_pushed': auto
                        })
                        
                        del self.pending_approvals[run_id]
                        
                        return {
                            'success': True,
                            'action': 'committed_and_pushed',
                            'commit': commit_result.get('commit_hash'),
                            'auto': auto
                        }
                    else:
                        logger.error(f"Push failed: {push_result.get('error')}")
                        return {
                            'success': False,
                            'error': f"Push failed: {push_result.get('error')}"
                        }
            else:
                logger.error(f"Commit failed: {commit_result.get('error')}")
                return {'success': False, 'error': commit_result.get('error')}
        
        except Exception as e:
            logger.error(f"Failed to commit/push: {e}")
            return {'success': False, 'error': str(e)}
    
    def _push_to_remote(self) -> Dict[str, Any]:
        """Push to remote repository"""
        
        if not self.repo:
            return {'success': False, 'error': 'No git repo'}
        
        try:
            # Get current branch
            current_branch = self.repo.active_branch.name
            
            # Push
            origin = self.repo.remote('origin')
            push_info = origin.push(current_branch)
            
            logger.info(f"Pushed to origin/{current_branch}")
            
            return {
                'success': True,
                'branch': current_branch,
                'push_info': str(push_info)
            }
        
        except Exception as e:
            logger.error(f"Push failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def _determine_risk_level(self, details: Dict[str, Any]) -> str:
        """Determine risk level from healing details"""
        
        evaluation = details.get('evaluation', {})
        patch = details.get('patch', {})
        
        # Check explicit risk level
        if 'risk_level' in evaluation:
            return evaluation['risk_level']
        
        # Determine based on patch size and confidence
        lines_changed = patch.get('metadata', {}).get('lines_changed', 0)
        confidence = evaluation.get('confidence', 0.5)
        
        if lines_changed > 20 or confidence < 0.7:
            return 'HIGH'
        elif lines_changed > 10 or confidence < 0.85:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def get_pending_approvals(self) -> list:
        """Get all pending approvals"""
        
        return [
            {
                'run_id': run_id,
                'file': data['file'],
                'risk': data['risk'],
                'timestamp': data['timestamp'].isoformat(),
                'requires_manual': data.get('requires_manual', False),
                'time_remaining': self._get_time_remaining(run_id)
            }
            for run_id, data in self.pending_approvals.items()
        ]
    
    def _get_time_remaining(self, run_id: str) -> Optional[float]:
        """Get time remaining for auto-push"""
        
        if run_id not in self.approval_timers:
            return None
        
        approval = self.pending_approvals.get(run_id)
        if not approval:
            return None
        
        elapsed = (datetime.now() - approval['timestamp']).total_seconds()
        remaining = max(0, self.low_risk_timeout - elapsed)
        
        return remaining


class GitChangeHandler(FileSystemEventHandler):
    """File system event handler for git changes"""
    
    def __init__(self, auto_healer: GitAutoHealer):
        self.auto_healer = auto_healer
        self.last_modified = {}
        self.debounce_seconds = 2  # Debounce rapid changes
    
    def on_modified(self, event):
        """Handle file modification"""
        
        if event.is_directory:
            return
        
        file_path = event.src_path
        
        # Debounce rapid changes
        now = time.time()
        last_mod = self.last_modified.get(file_path, 0)
        
        if now - last_mod < self.debounce_seconds:
            return
        
        self.last_modified[file_path] = now
        
        # Trigger healing
        self.auto_healer.on_file_changed(file_path)