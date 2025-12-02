import hmac
import hashlib
from typing import Dict, Any, Optional
from fastapi import Request, HTTPException

from utils.logger import get_logger

logger = get_logger(__name__)

class GitHubWebhookHandler:
    """Handle GitHub webhooks for CI integration"""
    
    def __init__(self, secret: Optional[str], pipeline):
        self.secret = secret
        self.pipeline = pipeline
    
    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """Verify webhook signature"""
        
        if not self.secret:
            logger.warning("No webhook secret configured, skipping verification")
            return True
        
        expected = 'sha256=' + hmac.new(
            self.secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected, signature)
    
    async def handle_webhook(self, request: Request) -> Dict[str, Any]:
        """Handle incoming webhook"""
        
        # Verify signature
        signature = request.headers.get('X-Hub-Signature-256', '')
        payload = await request.body()
        
        if not self.verify_signature(payload, signature):
            raise HTTPException(status_code=401, detail="Invalid signature")
        
        # Parse event
        event_type = request.headers.get('X-GitHub-Event', '')
        data = await request.json()
        
        logger.info(f"Received GitHub webhook: {event_type}")
        
        # Handle different event types
        if event_type == 'push':
            return await self.handle_push(data)
        elif event_type == 'pull_request':
            return await self.handle_pull_request(data)
        elif event_type == 'check_run':
            return await self.handle_check_run(data)
        else:
            return {"status": "ignored", "event": event_type}
    
    async def handle_push(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle push event"""
        
        commits = data.get('commits', [])
        repo = data.get('repository', {}).get('full_name', 'unknown')
        
        logger.info(f"Push to {repo}: {len(commits)} commits")
        
        # Could trigger healing on pushed files
        return {"status": "processed", "commits": len(commits)}
    
    async def handle_pull_request(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle pull request event"""
        
        action = data.get('action', '')
        pr = data.get('pull_request', {})
        
        if action in ['opened', 'synchronize']:
            # Could trigger healing on PR files
            logger.info(f"PR {pr.get('number')} {action}")
        
        return {"status": "processed", "action": action}
    
    async def handle_check_run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle check run (CI failure)"""
        
        check_run = data.get('check_run', {})
        conclusion = check_run.get('conclusion', '')
        
        if conclusion == 'failure':
            # Trigger self-healing for failed check
            logger.info("CI check failed, triggering self-healing")
            
            # Extract failure info and trigger healing
            # This is where you'd parse CI logs and trigger the pipeline
        
        return {"status": "processed", "conclusion": conclusion}