import os
import json
import uuid
from typing import Dict, Any, Optional
from datetime import datetime
from utils.logger import get_logger

logger = get_logger(__name__)

class ExperimentLogger:
    """Log experiments and iterations for analysis"""
    
    def __init__(self, config: Dict[str, Any]):
        self.log_dir = os.path.join(config.get('data_dir', 'data'), 'logs')
        os.makedirs(self.log_dir, exist_ok=True)
        
        self.current_runs = {}
    
    def start_run(self, metadata: Dict[str, Any]) -> str:
        """Start a new healing run"""
        
        run_id = str(uuid.uuid4())
        
        run_data = {
            "run_id": run_id,
            "start_time": datetime.utcnow().isoformat(),
            "metadata": metadata,
            "steps": [],
            "status": "running"
        }
        
        self.current_runs[run_id] = run_data
        
        logger.info(f"Started run: {run_id}")
        
        return run_id
    
    def log_step(self, run_id: str, step_name: str, data: Dict[str, Any]):
        """Log a step in the healing process"""
        
        if run_id not in self.current_runs:
            logger.warning(f"Run {run_id} not found")
            return
        
        step = {
            "name": step_name,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data
        }
        
        self.current_runs[run_id]["steps"].append(step)
        
        logger.debug(f"Logged step '{step_name}' for run {run_id}")
    
    def complete_run(self, run_id: str, result: Dict[str, Any]):
        """Complete a healing run"""
        
        if run_id not in self.current_runs:
            logger.warning(f"Run {run_id} not found")
            return
        
        run_data = self.current_runs[run_id]
        run_data["end_time"] = datetime.utcnow().isoformat()
        run_data["result"] = result
        run_data["status"] = "completed"
        
        # Calculate duration
        start = datetime.fromisoformat(run_data["start_time"])
        end = datetime.fromisoformat(run_data["end_time"])
        run_data["duration_seconds"] = (end - start).total_seconds()
        
        # Save to file
        self._save_run(run_data)
        
        # Remove from current runs
        del self.current_runs[run_id]
        
        logger.info(f"Completed run: {run_id} ({run_data['duration_seconds']:.2f}s)")
    
    def get_run(self, run_id: str) -> Optional[Dict[str, Any]]:
        """Get run data"""
        
        # Check current runs
        if run_id in self.current_runs:
            return self.current_runs[run_id]
        
        # Check saved runs
        run_file = os.path.join(self.log_dir, f"{run_id}.json")
        if os.path.exists(run_file):
            with open(run_file, 'r') as f:
                return json.load(f)
        
        return None
    
    def get_recent_runs(self, limit: int = 10) -> list:
        """Get recent runs"""
        
        runs = []
        
        # Get all run files
        run_files = [f for f in os.listdir(self.log_dir) if f.endswith('.json')]
        run_files.sort(reverse=True)  # Most recent first
        
        for run_file in run_files[:limit]:
            try:
                with open(os.path.join(self.log_dir, run_file), 'r') as f:
                    runs.append(json.load(f))
            except Exception as e:
                logger.warning(f"Could not load run file {run_file}: {e}")
        
        return runs
    
    def _save_run(self, run_data: Dict[str, Any]):
        """Save run data to file"""
        
        run_file = os.path.join(self.log_dir, f"{run_data['run_id']}.json")
        
        with open(run_file, 'w') as f:
            json.dump(run_data, f, indent=2)
        
        logger.debug(f"Saved run to {run_file}")