import json
from typing import Dict, Any, List
from datetime import datetime
from utils.logger import get_logger

logger = get_logger(__name__)

class NotificationService:
    """Manage notifications for healing events"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.notifications = []  # In-memory storage for web interface
        self.max_notifications = 100
    
    def send_success_notification(self, result: Dict[str, Any]):
        """Send notification for successful fix"""
        
        notification = {
            "id": self._generate_id(),
            "type": "success",
            "timestamp": datetime.utcnow().isoformat(),
            "title": "✅ Fix Applied Successfully",
            "message": f"Patch applied with {result.get('details', {}).get('patch', {}).get('metadata', {}).get('lines_changed', 'unknown')} lines changed",
            "details": result,
            "read": False
        }
        
        self._add_notification(notification)
        logger.info("Success notification sent")
    
    def send_escalation_notification(self, result: Dict[str, Any]):
        """Send notification for escalation"""
        
        notification = {
            "id": self._generate_id(),
            "type": "warning",
            "timestamp": datetime.utcnow().isoformat(),
            "title": "⚠️ Manual Review Required",
            "message": f"Patch escalated: {result.get('details', {}).get('reason', 'unknown reason')}",
            "details": result,
            "read": False,
            "requires_action": True
        }
        
        self._add_notification(notification)
        logger.info("Escalation notification sent")
    
    def send_approval_request(self, result: Dict[str, Any]):
        """Send notification requesting approval"""
        
        notification = {
            "id": self._generate_id(),
            "type": "info",
            "timestamp": datetime.utcnow().isoformat(),
            "title": "🔔 Approval Required",
            "message": f"Patch ready for review: {result.get('file', 'unknown file')}",
            "details": result,
            "read": False,
            "requires_action": True,
            "action_type": "approval"
        }
        
        self._add_notification(notification)
        logger.info("Approval request sent")
    
    def send_failure_notification(self, result: Dict[str, Any]):
        """Send notification for failure"""
        
        notification = {
            "id": self._generate_id(),
            "type": "error",
            "timestamp": datetime.utcnow().isoformat(),
            "title": "❌ Healing Failed",
            "message": f"Failed to heal: {result.get('details', {}).get('message', 'unknown error')}",
            "details": result,
            "read": False
        }
        
        self._add_notification(notification)
        logger.info("Failure notification sent")
    
    def get_unread_notifications(self) -> List[Dict[str, Any]]:
        """Get all unread notifications"""
        
        return [n for n in self.notifications if not n.get('read', False)]
    
    def get_all_notifications(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent notifications"""
        
        return self.notifications[:limit]
    
    def mark_as_read(self, notification_id: str):
        """Mark notification as read"""
        
        for notif in self.notifications:
            if notif['id'] == notification_id:
                notif['read'] = True
                logger.debug(f"Marked notification {notification_id} as read")
                break
    
    def _add_notification(self, notification: Dict[str, Any]):
        """Add notification to list"""
        
        self.notifications.insert(0, notification)
        
        # Keep only recent notifications
        if len(self.notifications) > self.max_notifications:
            self.notifications = self.notifications[:self.max_notifications]
    
    def _generate_id(self) -> str:
        """Generate notification ID"""
        
        import uuid
        return str(uuid.uuid4())