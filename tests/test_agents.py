"""Unit tests for agents"""

import pytest
import sys
import os

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_imports():
    """Test that all modules can be imported"""
    
    from agents.analyzer_agent import AnalyzerAgent
    from agents.planner_agent import PlannerAgent
    from agents.fixer_agent import FixerAgent
    from agents.tester_agent import TesterAgent
    from agents.critic_agent import CriticAgent
    from agents.manager_agent import ManagerAgent
    
    assert AnalyzerAgent is not None
    assert PlannerAgent is not None
    assert FixerAgent is not None
    assert TesterAgent is not None
    assert CriticAgent is not None
    assert ManagerAgent is not None

def test_services():
    """Test that all services can be imported"""
    
    from services.static_analysis import StaticAnalyzer
    from services.code_parser import CodeParser
    from services.test_runner import TestRunner
    from services.patch_applier import PatchApplier
    from services.experiment_logger import ExperimentLogger
    from services.dependency_analyzer import DependencyAnalyzer
    from services.learning_system import LearningSystem
    
    assert StaticAnalyzer is not None
    assert CodeParser is not None

def test_config():
    """Test configuration loading"""
    
    from utils.config import load_config
    
    config = load_config()
    
    assert 'models' in config
    assert 'healing' in config
    assert 'mistral' in config['models']

if __name__ == '__main__':
    pytest.main([__file__, '-v'])