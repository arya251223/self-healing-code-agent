from typing import Dict, Any, Optional

from agents.analyzer_agent import AnalyzerAgent
from agents.planner_agent import PlannerAgent
from agents.fixer_agent import FixerAgent
from agents.tester_agent import TesterAgent
from agents.critic_agent import CriticAgent
from agents.manager_agent import ManagerAgent

from models.load_mistral import MistralClient
from models.load_codellama import CodeLlamaClient
from models.load_starcoder import StarCoderClient

from services.static_analysis import StaticAnalyzer
from services.code_parser import CodeParser
from services.test_runner import TestRunner
from services.patch_applier import PatchApplier
from services.experiment_logger import ExperimentLogger
from services.dependency_analyzer import DependencyAnalyzer
from services.learning_system import LearningSystem
from services.notification_service import NotificationService

from utils.logger import get_logger

logger = get_logger(__name__)

def test_ollama_actually_works(config: Dict[str, Any]) -> bool:
    """Test if Ollama can actually respond (not just running)"""
    
    import requests
    
    try:
        host = config['models']['mistral']['host']
        
        # Test if server responds
        response = requests.get(f"{host}/api/tags", timeout=2)
        if response.status_code != 200:
            return False
        
        # Test if we can actually generate (quick test)
        test_payload = {
            "model": config['models']['mistral']['name'].split(':')[0],
            "prompt": "test",
            "stream": False,
            "options": {"num_predict": 1}
        }
        
        response = requests.post(
            f"{host}/api/generate",
            json=test_payload,
            timeout=5
        )
        
        return response.status_code == 200
        
    except Exception as e:
        logger.debug(f"Ollama test failed: {e}")
        return False

class SelfHealingPipeline:
    """Main pipeline for self-healing system"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        logger.info("Initializing Self-Healing Pipeline")
        
        # Initialize model clients with auto-fallback
        logger.info("Loading AI models...")
        
        # Test if Ollama actually works
        use_real_models = test_ollama_actually_works(config)
        
        if use_real_models:
            logger.info("✓ Ollama is working, using real models")
            try:
                self.mistral = MistralClient(config['models']['mistral'])
                self.codellama = CodeLlamaClient(config['models']['codellama'])
                self.starcoder = StarCoderClient(config['models']['starcoder'])
            except Exception as e:
                logger.warning(f"Failed to load real models: {e}, using mocks")
                use_real_models = False
        
        if not use_real_models:
            logger.warning("⚠️ Ollama not working properly, using MOCK models")
            from tests.run_demo import MockLLMClient, MockCodeLlamaClient, MockStarCoderClient
            self.mistral = MockLLMClient(config['models']['mistral'])
            self.codellama = MockCodeLlamaClient(config['models']['codellama'])
            self.starcoder = MockStarCoderClient(config['models']['starcoder'])
        
        # Initialize services
        logger.info("Initializing services...")
        self.test_runner = TestRunner(config)
        self.patch_applier = PatchApplier(config)
        self.experiment_logger = ExperimentLogger(config)
        self.dependency_analyzer = DependencyAnalyzer()
        self.learning_system = LearningSystem(config)
        self.notification_service = NotificationService(config)
        
        # Initialize agents
        logger.info("Initializing agents...")
        self.analyzer = AnalyzerAgent(self.mistral)
        self.planner = PlannerAgent(self.mistral)
        self.fixer = FixerAgent(self.codellama)
        self.tester = TesterAgent(self.starcoder, self.test_runner)
        self.critic = CriticAgent(self.mistral)
        
        # Initialize manager
        self.manager = ManagerAgent(
            analyzer=self.analyzer,
            planner=self.planner,
            fixer=self.fixer,
            tester=self.tester,
            critic=self.critic,
            patch_applier=self.patch_applier,
            experiment_logger=self.experiment_logger,
            dependency_analyzer=self.dependency_analyzer,
            learning_system=self.learning_system,
            notification_service=self.notification_service,
            config=config
        )
        
        logger.info("Pipeline initialized successfully!")
    
    def heal(self, 
             target_file: Optional[str] = None,
             stack_trace: Optional[str] = None,
             repo_path: str = ".",
             ci_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run self-healing process"""
        
        return self.manager.heal(
            target_file=target_file,
            stack_trace=stack_trace,
            repo_path=repo_path,
            ci_context=ci_context
        )