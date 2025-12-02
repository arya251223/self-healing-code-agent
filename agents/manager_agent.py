import json
import time
import os
from typing import Dict, Any, List, Optional
from datetime import datetime
from unittest import result

from agents.analyzer_agent import AnalyzerAgent
from agents.planner_agent import PlannerAgent
from agents.fixer_agent import FixerAgent
from agents.tester_agent import TesterAgent
from agents.critic_agent import CriticAgent

from services.patch_applier import PatchApplier
from services.experiment_logger import ExperimentLogger
from services.dependency_analyzer import DependencyAnalyzer
from services.learning_system import LearningSystem
from services.notification_service import NotificationService

from utils.logger import get_logger

logger = get_logger(__name__)

class ManagerAgent:
    """Orchestrator for the self-healing loop"""
    
    def __init__(self,
                 analyzer: AnalyzerAgent,
                 planner: PlannerAgent,
                 fixer: FixerAgent,
                 tester: TesterAgent,
                 critic: CriticAgent,
                 patch_applier: PatchApplier,
                 experiment_logger: ExperimentLogger,
                 dependency_analyzer: DependencyAnalyzer,
                 learning_system: LearningSystem,
                 notification_service: NotificationService,
                 config: Dict[str, Any]):
        
        self.analyzer = analyzer
        self.planner = planner
        self.fixer = fixer
        self.tester = tester
        self.critic = critic
        self.patch_applier = patch_applier
        self.experiment_logger = experiment_logger
        self.dependency_analyzer = dependency_analyzer
        self.learning_system = learning_system
        self.notification_service = notification_service
        self.config = config
        
        self.max_attempts = config.get('healing', {}).get('max_attempts', 5)
    
    def heal(self, 
             target_file: Optional[str] = None,
             stack_trace: Optional[str] = None,
             repo_path: str = ".",
             ci_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Main self-healing loop
        
        Args:
            target_file: Specific file to analyze
            stack_trace: Stack trace from failure
            repo_path: Path to repository
            ci_context: CI/CD context (PR, commit, etc.)
        
        Returns:
            Healing result with status and details
        """
        
        run_id = self.experiment_logger.start_run({
            "target_file": target_file,
            "has_trace": stack_trace is not None,
            "repo_path": repo_path,
            "ci_context": ci_context,
            "timestamp": datetime.utcnow().isoformat()
        })
        
        logger.info(f"Starting self-healing loop (run_id: {run_id})")
        
        try:
            # Phase 1: Analysis
            logger.info("Phase 1: Analyzing code")
            bug_report = self._analyze_phase(target_file, stack_trace, repo_path)
            
            if not bug_report.get('bugs'):
                return self._complete_run(run_id, "NO_BUGS_FOUND", {
                    "message": "No bugs detected",
                    "bug_report": bug_report
                })
            
            # Build repository context
            repo_context = self._build_repo_context(repo_path, bug_report)
            
            # Check learning system for similar past fixes
            similar_fixes = self.learning_system.find_similar_bugs(bug_report)
            if similar_fixes:
                logger.info(f"Found {len(similar_fixes)} similar past fixes")
            
            # Phase 2-7: Iterative repair loop
            attempt = 0
            previous_attempts = []
            
            while attempt < self.max_attempts:
                attempt += 1
                logger.info(f"Repair attempt {attempt}/{self.max_attempts}")
                
                try:
                    result = self._repair_iteration(
                        bug_report=bug_report,
                        repo_context=repo_context,
                        repo_path=repo_path,
                        previous_attempts=previous_attempts,
                        similar_fixes=similar_fixes,
                        run_id=run_id,
                        attempt=attempt
                    )
                    
                    if result['status'] == 'SUCCESS':
                        # Learn from successful fix
                        self.learning_system.record_success(bug_report, result)
                        
                        # Send notification
                        self.notification_service.send_success_notification(result)
                        
                        return self._complete_run(run_id, "SUCCESS", result)
                    
                    elif result['status'] == 'ESCALATE':
                        # Send notification for escalation
                        self.notification_service.send_escalation_notification(result)
                        
                        return self._complete_run(run_id, "ESCALATED", result)
                    
                    else:  # RETRY
                        # Add more context to attempt record
                        result['strategy'] = plan.get('strategy', 'unknown') if 'plan' in locals() else 'unknown'
                        result['failure_reason'] = result.get('error', result.get('feedback', {}).get('issue', 'Unknown'))
                        
                        previous_attempts.append(result)
                        # Learn from failure
                        self.learning_system.record_failure(bug_report, result)
                
                except Exception as e:
                    logger.error(f"Attempt {attempt} failed with exception: {e}")
                    previous_attempts.append({
                        "attempt": attempt,
                        "error": str(e),
                        "status": "ERROR"
                    })
            
            # Max attempts reached
            return self._complete_run(run_id, "MAX_ATTEMPTS_REACHED", {
                "message": f"Failed after {self.max_attempts} attempts",
                "attempts": previous_attempts
            })
        
        except Exception as e:
            logger.error(f"Self-healing loop failed: {e}", exc_info=True)
            return self._complete_run(run_id, "FAILED", {
                "error": str(e),
                "traceback": str(e.__traceback__)
            })
        
    
    def _analyze_phase(self, 
                       target_file: Optional[str],
                       stack_trace: Optional[str],
                       repo_path: str) -> Dict[str, Any]:
        """Phase 1: Analyze code for bugs"""
        
        if stack_trace:
            # Parse stack trace to find files
            files = self.dependency_analyzer.parse_trace_files(stack_trace, repo_path)
            bug_report = self.analyzer.analyze_trace(stack_trace, files)
        elif target_file:
            bug_report = self.analyzer.analyze_file(target_file)
        else:
            # Analyze entire repo (or recent changes)
            bug_report = self._analyze_repo(repo_path)
        
        return bug_report
    
    def _repair_iteration(self,
                          bug_report: Dict[str, Any],
                          repo_context: Dict[str, Any],
                          repo_path: str,
                          previous_attempts: List[Dict[str, Any]],
                          similar_fixes: List[Dict[str, Any]],
                          run_id: str,
                          attempt: int) -> Dict[str, Any]:
        """Single iteration of the repair loop"""
        
        iteration_start = time.time()
        
        # Phase 2: Planning
        logger.info("Phase 2: Creating repair plan")
        plan = self.planner.make_plan(bug_report, repo_context, previous_attempts)
        
        # Validate plan has required fields
        if not plan.get('target_file') or plan.get('strategy') == 'none':
            logger.warning("Invalid or null plan generated")
            return {
                "status": "RETRY",
                "attempt": attempt,
                "phase": "planning",
                "error": "Could not create valid repair plan",
                "feedback": {
                    "issue": "Planning failed",
                    "suggestion": "Try different analysis approach"
                }
            }
        
        self.experiment_logger.log_step(run_id, "plan", {
            "attempt": attempt,
            "plan": plan
        })
        
        # Phase 3: Generate patch
        logger.info(f"Phase 3: Generating patch ({plan['strategy']})")
        
        # Get target file content
        target_file = plan.get('target_file')
        
        # Validate file exists and is readable
        if not target_file or not os.path.exists(target_file):
            logger.error(f"Target file not found: {target_file}")
            return {
                "status": "RETRY",
                "attempt": attempt,
                "phase": "file_validation",
                "error": f"File not found: {target_file}",
                "feedback": {
                    "issue": "Target file invalid",
                    "suggestion": "Verify file path in bug report"
                }
            }
        
        try:
            with open(target_file, 'r', encoding='utf-8') as f:
                file_content = f.read()
        except Exception as e:
            logger.error(f"Could not read file {target_file}: {e}")
            return {
                "status": "RETRY",
                "attempt": attempt,
                "phase": "file_reading",
                "error": str(e),
                "feedback": {
                    "issue": "Could not read target file",
                    "suggestion": "Check file permissions and encoding"
                }
            }
        
        # Generate patch
        try:
            patch = self.fixer.generate_patch(
                file_path=target_file,
                file_content=file_content,
                plan=plan,
                bug_report=bug_report
            )
        except Exception as e:
            logger.error(f"Patch generation failed: {e}")
            return {
                "status": "RETRY",
                "attempt": attempt,
                "phase": "patch_generation",
                "error": str(e),
                "feedback": {
                    "issue": "Patch generation failed",
                    "details": str(e),
                    "suggestion": "Try simpler fix strategy"
                }
            }
        
        self.experiment_logger.log_step(run_id, "patch", {
            "attempt": attempt,
            "patch": patch
        })
        
        # Phase 4: Dry-apply and validate
        logger.info("Phase 4: Validating patch")
        apply_result = self.patch_applier.dry_apply(
            patch=patch['patch'],
            target_file=target_file
        )
        
        if not apply_result['success']:
            logger.warning(f"Patch validation failed: {apply_result['error']}")
            return {
                "status": "RETRY",
                "attempt": attempt,
                "phase": "validation",
                "error": apply_result['error'],
                "feedback": {
                    "issue": "Patch failed validation",
                    "details": apply_result['error'],
                    "suggestion": "Generate syntactically correct patch"
                }
            }
        
        # Phase 5: Apply patch temporarily
        logger.info("Phase 5: Applying patch")
        self.patch_applier.apply(patch['patch'], target_file)
        
        try:
            # Phase 6: Run tests
            logger.info("Phase 6: Running tests")
            test_results = self.tester.run_tests(
                patch=patch,
                repo_path=repo_path,
                plan=plan
            )
            
            self.experiment_logger.log_step(run_id, "test", {
                "attempt": attempt,
                "results": test_results
            })
            
            # Phase 7: Critic evaluation
            logger.info("Phase 7: Evaluating patch quality")
            evaluation = self.critic.evaluate_patch(
                patch=patch,
                test_results=test_results,
                bug_report=bug_report,
                plan=plan,
                config=self.config
            )
            
            self.experiment_logger.log_step(run_id, "evaluation", {
                "attempt": attempt,
                "evaluation": evaluation
            })
            
            # Decide next action
            if evaluation['verdict'] == 'PASS':
                # Check if should auto-merge
                if evaluation.get('should_auto_merge', False):
                    logger.info("Auto-merging patch")
                    commit_result = self.patch_applier.commit(
                        message=f"Auto-fix: {plan['issue_description']}",
                        run_id=run_id
                    )
                    
                    return {
                        "status": "SUCCESS",
                        "attempt": attempt,
                        "patch": patch,
                        "evaluation": evaluation,
                        "commit": commit_result,
                        "auto_merged": True,
                        "duration": time.time() - iteration_start
                    }
                else:
                    # Require approval
                    logger.info("Patch requires human approval")
                    
                    return {
                        "status": "SUCCESS",
                        "attempt": attempt,
                        "patch": patch,
                        "evaluation": evaluation,
                        "requires_approval": True,
                        "auto_merged": False,
                        "duration": time.time() - iteration_start
                    }
            
            elif evaluation['verdict'] == 'RETRY':
                # Rollback and retry
                self.patch_applier.rollback()
                
                return {
                    "status": "RETRY",
                    "attempt": attempt,
                    "evaluation": evaluation,
                    "feedback": {
                        "issues": evaluation.get('issues_found', []),
                        "suggestions": evaluation.get('suggestions', [])
                    },
                    "duration": time.time() - iteration_start
                }
            
            else:  # ESCALATE
                self.patch_applier.rollback()
                
                return {
                    "status": "ESCALATE",
                    "attempt": attempt,
                    "evaluation": evaluation,
                    "reason": evaluation.get('rationale', 'Unknown'),
                    "duration": time.time() - iteration_start
                }
        
        except Exception as e:
            # Rollback on any error
                logger.error(f"Error during repair iteration: {e}")
            
            # Try to rollback
                try:
                    self.patch_applier.rollback()
                except:
                    pass
            
            # Return retry with error info
                return {
                    "status": "RETRY",
                    "attempt": attempt,
                    "phase": "unknown",
                    "error": str(e),
                    "feedback": {
                        "issue": f"Iteration failed: {type(e).__name__}",
                        "details": str(e),
                        "suggestion": "Try different strategy"
                    },
                    "duration": time.time() - iteration_start
                }
    
    def _build_repo_context(self, repo_path: str, bug_report: Dict[str, Any]) -> Dict[str, Any]:
        """Build repository context for planning"""
        
        affected_files = [bug['file'] for bug in bug_report.get('bugs', []) if bug.get('file')]
        
        return {
            "project_type": self.dependency_analyzer.detect_project_type(repo_path),
            "language": "Python",
            "test_framework": self.dependency_analyzer.detect_test_framework(repo_path),
            "dependencies": self.dependency_analyzer.get_dependencies(repo_path),
            "affected_files": affected_files,
            "dependency_graph": self.dependency_analyzer.build_dependency_graph(affected_files) if affected_files else {}
        }
    
    def _analyze_repo(self, repo_path: str) -> Dict[str, Any]:
        """Analyze entire repository for bugs"""
        
        # This would be a more comprehensive analysis
        # For now, return empty bug report
        logger.warning("Full repo analysis not implemented, returning empty report")
        return {
            "bugs": [],
            "summary": "No target specified",
            "confidence": 0.0
        }
    
    def _complete_run(self, run_id: str, status: str, details: Dict[str, Any]) -> Dict[str, Any]:
        """Complete the healing run and log results"""
    
        result = {
            "run_id": run_id,
            "status": status,
            "details": details,
            "timestamp": datetime.utcnow().isoformat()
        }
    
        self.experiment_logger.complete_run(run_id, result)
    
        logger.info(f"Healing run completed: {status} (run_id: {run_id})")
    
    # Send appropriate notification based on status
        if status == "SUCCESS":
            self.notification_service.send_success_notification(result)
        elif status == "ESCALATED":
            self.notification_service.send_escalation_notification(result)
        elif status in ["FAILED", "MAX_ATTEMPTS_REACHED"]:
            self.notification_service.send_failure_notification(result)
    
        return result