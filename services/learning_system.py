import os
import json
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False
    
from utils.logger import get_logger

logger = get_logger(__name__)

class LearningSystem:
    """Learn from past fixes to improve future repairs"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.enabled = config.get('learning', {}).get('enabled', True)
        self.memory_dir = os.path.join(config.get('data_dir', 'data'), 'memory')
        os.makedirs(self.memory_dir, exist_ok=True)
        
        # Initialize vector store if available
        if CHROMADB_AVAILABLE and self.enabled:
            self._init_vector_store()
        else:
            self.vector_store = None
            if self.enabled:
                logger.warning("ChromaDB not available, using simple JSON storage")
    
    def _init_vector_store(self):
        """Initialize ChromaDB vector store"""
    
        try:
            # Use new Client API
            from chromadb import Client
            from chromadb.config import Settings as ChromaSettings
        
            self.chroma_client = Client(ChromaSettings(
                anonymized_telemetry=False,
                allow_reset=True
            ))
        
            self.collection = self.chroma_client.get_or_create_collection(
                name="bug_fixes",
                metadata={"description": "Historical bug fixes for learning"}
            )
        
            logger.info("ChromaDB vector store initialized")
        except Exception as e:
            logger.warning(f"ChromaDB not available: {e}. Using simple storage.")
            self.vector_store = None
    
    def record_success(self, bug_report: Dict[str, Any], result: Dict[str, Any]):
        """Record successful fix for future learning"""
        
        if not self.enabled:
            return
        
        logger.info("Recording successful fix")
        
        record = {
            "id": self._generate_id(bug_report),
            "timestamp": datetime.utcnow().isoformat(),
            "bug_report": bug_report,
            "result": result,
            "success": True
        }
        
        # Save to JSON
        self._save_record(record)
        
        # Add to vector store if available
        if CHROMADB_AVAILABLE and hasattr(self, 'collection'):
            self._add_to_vector_store(record)
    
    def record_failure(self, bug_report: Dict[str, Any], result: Dict[str, Any]):
        """Record failed attempt to avoid repeating"""
        
        if not self.enabled:
            return
        
        logger.info("Recording failed attempt")
        
        record = {
            "id": self._generate_id(bug_report),
            "timestamp": datetime.utcnow().isoformat(),
            "bug_report": bug_report,
            "result": result,
            "success": False
        }
        
        self._save_record(record)
    
    def find_similar_bugs(self, bug_report: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
        """Find similar past bugs and their fixes"""
        
        if not self.enabled:
            return []
        
        logger.info("Searching for similar past bugs")
        
        # Use vector search if available
        if CHROMADB_AVAILABLE and hasattr(self, 'collection'):
            return self._vector_search(bug_report, limit)
        else:
            return self._simple_search(bug_report, limit)
    
    def get_success_rate(self, strategy: str) -> float:
        """Get success rate for a specific strategy"""
        
        records = self._load_all_records()
        
        strategy_records = [
            r for r in records 
            if r.get('result', {}).get('patch', {}).get('strategy') == strategy
        ]
        
        if not strategy_records:
            return 0.0
        
        successes = sum(1 for r in strategy_records if r.get('success', False))
        
        return successes / len(strategy_records)
    
    def _vector_search(self, bug_report: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
        """Search using vector similarity"""
        
        try:
            # Create query from bug report
            query_text = self._bug_report_to_text(bug_report)
            
            # Query vector store
            results = self.collection.query(
                query_texts=[query_text],
                n_results=limit,
                where={"success": True}  # Only successful fixes
            )
            
            # Convert to records
            similar = []
            if results['ids'] and results['ids'][0]:
                for i, doc_id in enumerate(results['ids'][0]):
                    record = self._load_record(doc_id)
                    if record:
                        record['similarity'] = 1.0 - results['distances'][0][i]
                        similar.append(record)
            
            return similar
        
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []
    
    def _simple_search(self, bug_report: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
        """Simple keyword-based search"""
        
        records = self._load_all_records()
        
        # Only successful fixes
        successes = [r for r in records if r.get('success', False)]
        
        if not successes:
            return []
        
        # Calculate simple similarity based on error types and symptoms
        query_errors = set(bug['symptom'] for bug in bug_report.get('bugs', []))
        
        scored = []
        for record in successes:
            record_errors = set(bug['symptom'] for bug in record.get('bug_report', {}).get('bugs', []))
            
            # Jaccard similarity
            if query_errors and record_errors:
                intersection = len(query_errors & record_errors)
                union = len(query_errors | record_errors)
                similarity = intersection / union if union > 0 else 0.0
            else:
                similarity = 0.0
            
            if similarity > 0:
                record['similarity'] = similarity
                scored.append(record)
        
        # Sort by similarity
        scored.sort(key=lambda x: x['similarity'], reverse=True)
        
        return scored[:limit]
    
    def _bug_report_to_text(self, bug_report: Dict[str, Any]) -> str:
        """Convert bug report to text for embedding"""
        
        texts = []
        
        for bug in bug_report.get('bugs', []):
            text = f"{bug.get('symptom', '')} {bug.get('root_cause', '')} {bug.get('suggested_fix', '')}"
            texts.append(text)
        
        return " ".join(texts)
    
    def _add_to_vector_store(self, record: Dict[str, Any]):
        """Add record to vector store"""
        
        try:
            text = self._bug_report_to_text(record['bug_report'])
            
            self.collection.add(
                documents=[text],
                metadatas=[{
                    "success": record['success'],
                    "timestamp": record['timestamp']
                }],
                ids=[record['id']]
            )
        except Exception as e:
            logger.error(f"Failed to add to vector store: {e}")
    
    def _generate_id(self, bug_report: Dict[str, Any]) -> str:
        """Generate unique ID for bug report"""
        
        # Use hash of bug symptoms
        text = self._bug_report_to_text(bug_report)
        return hashlib.md5(text.encode()).hexdigest()
    
    def _save_record(self, record: Dict[str, Any]):
        """Save record to JSON file"""
        
        record_file = os.path.join(self.memory_dir, f"{record['id']}.json")
        
        with open(record_file, 'w') as f:
            json.dump(record, f, indent=2)
    
    def _load_record(self, record_id: str) -> Optional[Dict[str, Any]]:
        """Load record from JSON file"""
        
        record_file = os.path.join(self.memory_dir, f"{record_id}.json")
        
        if os.path.exists(record_file):
            with open(record_file, 'r') as f:
                return json.load(f)
        
        return None
    
    def _load_all_records(self) -> List[Dict[str, Any]]:
        """Load all records"""
        
        records = []
        
        for filename in os.listdir(self.memory_dir):
            if filename.endswith('.json'):
                try:
                    with open(os.path.join(self.memory_dir, filename), 'r') as f:
                        records.append(json.load(f))
                except Exception as e:
                    logger.warning(f"Could not load {filename}: {e}")
        
        return records