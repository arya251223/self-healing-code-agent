from fastapi import FastAPI, WebSocket, HTTPException, BackgroundTasks
from integrations.git_auto_healer import GitAutoHealer
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.requests import Request
from pydantic import BaseModel
from typing import Optional, Dict, Any
import asyncio
import os

from pipelines.self_heal_loop import SelfHealingPipeline
from services.experiment_logger import ExperimentLogger
from services.notification_service import NotificationService
from utils.logger import get_logger
from utils.config import load_config

logger = get_logger(__name__)

# Initialize FastAPI
app = FastAPI(title="Self-Healing Code Agent", version="1.0.0")

# Load config
config = load_config()

# Initialize pipeline
pipeline = SelfHealingPipeline(config)
auto_healer = GitAutoHealer(pipeline, config)
# Get services
experiment_logger = pipeline.experiment_logger
notification_service = pipeline.notification_service

# Templates
templates = Jinja2Templates(directory="interface/web/templates")

# Static files
app.mount("/static", StaticFiles(directory="interface/web/static"), name="static")

# WebSocket connections for real-time updates
active_connections = []

# Models
class HealRequest(BaseModel):
    target_file: Optional[str] = None
    stack_trace: Optional[str] = None
    repo_path: str = "."
    
class ApprovalRequest(BaseModel):
    run_id: str
    approved: bool
    comment: Optional[str] = None

# Routes

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main dashboard"""
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    """Dashboard page"""
    recent_runs = experiment_logger.get_recent_runs(limit=10)
    unread_notifications = notification_service.get_unread_notifications()
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "recent_runs": recent_runs,
        "unread_count": len(unread_notifications)
    })

@app.get("/patch-review/{run_id}", response_class=HTMLResponse)
async def patch_review(request: Request, run_id: str):
    """Patch review page"""
    run_data = experiment_logger.get_run(run_id)
    
    if not run_data:
        raise HTTPException(status_code=404, detail="Run not found")
    
    return templates.TemplateResponse("patch_review.html", {
        "request": request,
        "run": run_data
    })

@app.post("/api/heal")
async def trigger_heal(request: HealRequest, background_tasks: BackgroundTasks):
    """Trigger self-healing process"""
    
    # Fix: Use model_dump() instead of dict()
    logger.info(f"Heal request received: {request.model_dump()}")
    
    # Run in background
    background_tasks.add_task(
        run_healing,
        request.target_file,
        request.stack_trace,
        request.repo_path
    )
    
    return {"status": "started", "message": "Self-healing process started"}

@app.post("/api/approve")
async def approve_patch(request: ApprovalRequest):
    """Approve or reject a patch"""
    
    logger.info(f"Approval request for run {request.run_id}: {request.approved}")
    
    run_data = experiment_logger.get_run(request.run_id)
    
    if not run_data:
        raise HTTPException(status_code=404, detail="Run not found")
    
    if request.approved:
        # Apply the patch
        result = pipeline.manager.patch_applier.commit(
            message=f"Approved fix from run {request.run_id}",
            run_id=request.run_id
        )
        
        # Update run data
        run_data['approved'] = True
        run_data['approval_comment'] = request.comment
        experiment_logger.complete_run(request.run_id, run_data)
        
        return {"status": "approved", "commit": result}
    else:
        # Reject and rollback
        pipeline.manager.patch_applier.rollback()
        
        run_data['approved'] = False
        run_data['approval_comment'] = request.comment
        experiment_logger.complete_run(request.run_id, run_data)
        
        return {"status": "rejected"}

@app.get("/api/runs")
async def get_runs(limit: int = 20):
    """Get recent healing runs"""
    
    runs = experiment_logger.get_recent_runs(limit=limit)
    return {"runs": runs}

@app.get("/api/runs/{run_id}")
async def get_run(run_id: str):
    """Get specific run details"""
    
    run_data = experiment_logger.get_run(run_id)
    
    if not run_data:
        raise HTTPException(status_code=404, detail="Run not found")
    
    return run_data

@app.get("/api/notifications")
async def get_notifications(unread_only: bool = False):
    """Get notifications"""
    
    if unread_only:
        notifications = notification_service.get_unread_notifications()
    else:
        notifications = notification_service.get_all_notifications()
    
    return {"notifications": notifications}

@app.post("/api/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str):
    """Mark notification as read"""
    
    notification_service.mark_as_read(notification_id)
    return {"status": "success"}

@app.get("/api/stats")
async def get_stats():
    """Get system statistics"""
    
    runs = experiment_logger.get_recent_runs(limit=100)
    
    total_runs = len(runs)
    successful = sum(1 for r in runs if r.get('result', {}).get('status') == 'SUCCESS')
    failed = sum(1 for r in runs if r.get('result', {}).get('status') in ['FAILED', 'MAX_ATTEMPTS_REACHED'])
    escalated = sum(1 for r in runs if r.get('result', {}).get('status') == 'ESCALATED')
    
    avg_duration = sum(r.get('duration_seconds', 0) for r in runs) / max(total_runs, 1)
    
    return {
        "total_runs": total_runs,
        "successful": successful,
        "failed": failed,
        "escalated": escalated,
        "success_rate": successful / max(total_runs, 1),
        "avg_duration": avg_duration
    }

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time updates"""
    
    await websocket.accept()
    active_connections.append(websocket)
    
    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except:
        active_connections.remove(websocket)

    @app.post("/api/auto-healing/start")
    async def start_auto_healing():
        """Start automatic healing mode"""
    
        auto_healer.start_auto_healing()
        return {"status": "started", "message": "Auto-healing activated"}

    @app.post("/api/auto-healing/stop")
    async def stop_auto_healing():
        """Stop automatic healing mode"""
    
        auto_healer.stop_auto_healing()
        return {"status": "stopped", "message": "Auto-healing deactivated"}
    @app.get("/api/auto-healing/status")
    async def auto_healing_status():
        """Get auto-healing status"""
    
        return {
            "enabled": auto_healer.is_running,
            "pending_approvals": auto_healer.get_pending_approvals()
        }

    @app.post("/api/auto-healing/approve/{run_id}")
    async def approve_auto_push(run_id: str, approve: bool = True):
        """Approve or reject auto-push"""
    
        result = auto_healer.approve_and_push(run_id, approved=approve, auto=False)
        return result
    @app.get("/api/auto-healing/pending")
    async def get_pending_approvals():
        """Get pending approval requests"""
    
        pending = auto_healer.get_pending_approvals()
        return {"pending": pending}
async def broadcast_update(message: Dict[str, Any]):
    """Broadcast update to all connected clients"""
    
    for connection in active_connections:
        try:
            await connection.send_json(message)
        except:
            active_connections.remove(connection)

def run_healing(target_file: Optional[str], stack_trace: Optional[str], repo_path: str):
    """Run healing process"""
    
    try:
        result = pipeline.heal(
            target_file=target_file,
            stack_trace=stack_trace,
            repo_path=repo_path
        )
        
        # Send notification based on result
        if result['status'] == 'SUCCESS':
            if result['details'].get('requires_approval'):
                notification_service.send_approval_request(result)
            else:
                notification_service.send_success_notification(result)
        elif result['status'] == 'ESCALATED':
            notification_service.send_escalation_notification(result)
        
        # Broadcast update
        asyncio.run(broadcast_update({
            "type": "healing_complete",
            "result": result
        }))
        
    except Exception as e:
        logger.error(f"Healing failed: {e}", exc_info=True)
        asyncio.run(broadcast_update({
            "type": "healing_error",
            "error": str(e)
        }))

# Auto-healing endpoints (add these)
@app.post("/api/auto-healing/start")
async def start_auto_healing():
    """Start automatic healing mode"""
    
    try:
        auto_healer.start_auto_healing()
        return {"status": "started", "message": "Auto-healing activated"}
    except Exception as e:
        logger.error(f"Failed to start auto-healing: {e}")
        return {"status": "error", "message": str(e)}

@app.post("/api/auto-healing/stop")
async def stop_auto_healing():
    """Stop automatic healing mode"""
    
    try:
        auto_healer.stop_auto_healing()
        return {"status": "stopped", "message": "Auto-healing deactivated"}
    except Exception as e:
        logger.error(f"Failed to stop auto-healing: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/api/auto-healing/status")
async def auto_healing_status():
    """Get auto-healing status"""
    
    return {
        "enabled": auto_healer.is_running,
        "pending_approvals": auto_healer.get_pending_approvals()
    }

@app.post("/api/auto-healing/approve/{run_id}")
async def approve_auto_push(run_id: str, approve: bool = True):
    """Approve or reject auto-push"""
    
    result = auto_healer.approve_and_push(run_id, approved=approve, auto=False)
    return result

@app.get("/api/auto-healing/pending")
async def get_pending_approvals():
    """Get pending approval requests"""
    
    pending = auto_healer.get_pending_approvals()
    return {"pending": pending}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)