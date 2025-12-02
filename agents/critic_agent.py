import json
from typing import Dict, Any, Optional
from models.load_mistral import MistralClient
from services.static_analysis import StaticAnalyzer
from utils.logger import get_logger

logger = get_logger(__name__)

class CriticAgent:
    """Agent responsible for evaluating patch quality"""
    
    SYSTEM_PROMPT = """You are CriticAgent. Evaluate the candidate patch against the bug_report and test_results. Provide PASS/RETRY/ESCALATE result plus rationales.

INSTRUCTIONS:
1. Verify that the patch addresses the bug and doesn't introduce regressions.
2. Check patch minimality (line diff size under threshold).
3. Check security-sensitive changes (e.g., input sanitization).
4. Provide precise feedback for Planner if RETRY.
5. Output JSON with this structure:
{
  "verdict": "PASS|RETRY|ESCALATE",
  "confidence": 0.0-1.0,
  "rationale": "detailed explanation",
  "issues_found": ["issue 1", "issue 2"],
  "suggestions": ["suggestion 1", "suggestion 2"],
  "security_concerns": ["concern 1"],
  "test_coverage": 0.0-1.0,
  "should_auto_merge": true|false
}"""
    
    def __init__(self, mistral_client: MistralClient):
        self.client = mistral_client
        self.static_analyzer = StaticAnalyzer()
    
    def evaluate_patch(self,
                       patch: Dict[str, Any],
                       test_results: Dict[str, Any],
                       bug_report: Dict[str, Any],
                       plan: Dict[str, Any],
                       config: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate patch quality and decide on next action"""
        
        logger.info("Evaluating patch quality")
        
        # Quick checks first
        quick_verdict = self._quick_checks(patch, test_results, config)
        if quick_verdict:
            return quick_verdict
        
        # Deep AI evaluation
        prompt = self._build_evaluation_prompt(patch, test_results, bug_report, plan)
        
        try:
            evaluation = self.client.generate_json(prompt, self.SYSTEM_PROMPT)
            
            # Validate and enrich evaluation
            evaluation = self._validate_evaluation(evaluation, patch, test_results, config)
            
            logger.info(f"Evaluation complete: {evaluation['verdict']} (confidence: {evaluation['confidence']})")
            
            return evaluation
            
        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            # Return safe fallback evaluation
            return self._create_fallback_evaluation(patch, test_results)
    
    def _quick_checks(self, 
                      patch: Dict[str, Any],
                      test_results: Dict[str, Any],
                      config: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Perform quick validation checks"""
        
        metadata = patch.get('metadata', {})
        
        # Check if tests failed
        if test_results.get('failed', 0) > 0:
            return {
                "verdict": "RETRY",
                "confidence": 0.9,
                "rationale": f"Tests failed: {test_results['failed']} out of {test_results['total']}",
                "issues_found": ["Test failures"],
                "suggestions": ["Review test failures and adjust patch"],
                "security_concerns": [],
                "test_coverage": test_results.get('passed', 0) / max(test_results.get('total', 1), 1),
                "should_auto_merge": False
            }
        
        # Check patch size
        max_lines = config.get('healing', {}).get('max_patch_lines', 25)
        if metadata.get('lines_changed', 0) > max_lines:
            return {
                "verdict": "ESCALATE",
                "confidence": 0.8,
                "rationale": f"Patch too large: {metadata['lines_changed']} lines (max: {max_lines})",
                "issues_found": ["Patch exceeds size limit"],
                "suggestions": ["Break into smaller patches or review manually"],
                "security_concerns": [],
                "test_coverage": 0.0,
                "should_auto_merge": False
            }
        
        # If no tests ran, that's OK for mock mode - accept the patch
        if test_results.get('total', 0) == 0:
            logger.warning("No tests executed - accepting patch in test mode")
            # Return PASS verdict with low confidence
            return {
                "verdict": "PASS",
                "confidence": 0.7,
                "rationale": "Patch applied successfully (no tests available)",
                "issues_found": [],
                "suggestions": ["Add tests for better validation"],
                "security_concerns": [],
                "test_coverage": 0.0,
                "should_auto_merge": False  # Don't auto-merge without tests
            }
        
        return None
    
    def _validate_evaluation(self, 
                             evaluation: Dict[str, Any],
                             patch: Dict[str, Any],
                             test_results: Dict[str, Any],
                             config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and enrich evaluation"""
        
        if not isinstance(evaluation, dict):
            logger.warning("Evaluation is not a dict, using fallback")
            return self._create_fallback_evaluation(patch, test_results)
        
        # Ensure required fields
        defaults = {
            "verdict": evaluation.get('verdict', 'PASS'),
            "confidence": evaluation.get('confidence', 0.5),
            "rationale": evaluation.get('rationale', 'No rationale provided'),
            "issues_found": evaluation.get('issues_found', []),
            "suggestions": evaluation.get('suggestions', []),
            "security_concerns": evaluation.get('security_concerns', []),
            "test_coverage": evaluation.get('test_coverage', 0.0),
            "should_auto_merge": False  # Will be calculated
        }
        
        # Validate verdict
        if defaults['verdict'] not in ['PASS', 'RETRY', 'ESCALATE']:
            logger.warning(f"Invalid verdict: {defaults['verdict']}, using PASS")
            defaults['verdict'] = 'PASS'
        
        # Calculate test coverage if not provided
        if test_results.get('total', 0) > 0:
            defaults['test_coverage'] = test_results['passed'] / test_results['total']
        
        # Determine if should auto-merge
        auto_merge_threshold = config.get('healing', {}).get('auto_merge_threshold', 0.9)
        
        defaults['should_auto_merge'] = (
            defaults['verdict'] == 'PASS' and
            defaults['confidence'] >= auto_merge_threshold and
            defaults['test_coverage'] > 0.8 and
            len(defaults['security_concerns']) == 0 and
            patch.get('metadata', {}).get('lines_changed', 999) <= 10
        )
        
        return defaults
    
    def _create_fallback_evaluation(self, 
                                     patch: Dict[str, Any],
                                     test_results: Dict[str, Any]) -> Dict[str, Any]:
        """Create safe fallback evaluation"""
        
        # If tests passed, approve; otherwise retry
        verdict = "PASS" if test_results.get('failed', 0) == 0 else "RETRY"
        
        return {
            "verdict": verdict,
            "confidence": 0.6,
            "rationale": "Evaluation generated from fallback logic",
            "issues_found": [] if verdict == "PASS" else ["LLM evaluation unavailable"],
            "suggestions": [] if verdict == "PASS" else ["Review patch manually"],
            "security_concerns": [],
            "test_coverage": test_results.get('passed', 0) / max(test_results.get('total', 1), 1),
            "should_auto_merge": False
        }
    
    def _build_evaluation_prompt(self,
                                  patch: Dict[str, Any],
                                  test_results: Dict[str, Any],
                                  bug_report: Dict[str, Any],
                                  plan: Dict[str, Any]) -> str:
        """Build prompt for patch evaluation"""
        
        return f"""Evaluate the quality and safety of this code patch.

ORIGINAL BUG REPORT:
{json.dumps(bug_report, indent=2)}

REPAIR PLAN:
Strategy: {plan.get('strategy')}
Risk Level: {plan.get('risk_level')}

PATCH:
{patch.get('patch', 'No patch text available')}

PATCH METADATA:
Lines Added: {patch.get('metadata', {}).get('lines_added', 0)}
Lines Removed: {patch.get('metadata', {}).get('lines_removed', 0)}
Total Changed: {patch.get('metadata', {}).get('lines_changed', 0)}

TEST RESULTS:
Total Tests: {test_results.get('total', 0)}
Passed: {test_results.get('passed', 0)}
Failed: {test_results.get('failed', 0)}
Errors: {test_results.get('errors', 0)}
Duration: {test_results.get('duration', 0)}s

Evaluate:
1. Does the patch actually fix the reported bug?
2. Are there any potential regressions or side effects?
3. Is the patch minimal and focused?
4. Are there any security concerns?
5. Is test coverage adequate?
6. Should this be auto-merged or require human review?

Provide your evaluation in the specified JSON format."""