

## 📄 **2. Complete `agents/planner_agent.py`**


import json
from typing import Dict, Any, List, Optional
from models.load_mistral import MistralClient
from utils.logger import get_logger

logger = get_logger(__name__)

class PlannerAgent:
    """Agent responsible for planning repair strategies"""
    
    SYSTEM_PROMPT = """You are PlannerAgent. Given a bug_report and repository context, produce a repair strategy.

INSTRUCTIONS:
1. Propose minimal change (one-line, function-level, or test addition).
2. Specify required tests (if any).
3. Provide risk estimate and timeout.
4. Output plan JSON with this structure:
{
  "strategy": "one_line_fix|function_replace|add_guard|add_test|refactor",
  "target_function": "function_name",
  "target_file": "path/to/file.py",
  "line_range": [start, end],
  "issue_description": "what needs fixing",
  "fix_approach": "how to fix it",
  "tests_needed": ["test description 1", "test description 2"],
  "risk_level": "LOW|MEDIUM|HIGH",
  "confidence": 0.0-1.0,
  "timeout_secs": 30,
  "dependencies": ["file1.py", "file2.py"],
  "rollback_steps": ["step 1", "step 2"]
}"""
    
    def __init__(self, mistral_client: MistralClient):
        self.client = mistral_client
        self.strategy_priority = [
            "one_line_fix",
            "add_guard",
            "function_replace",
            "add_test",
            "refactor"
        ]
    
    def make_plan(self, 
                  bug_report: Dict[str, Any], 
                  repo_context: Dict[str, Any],
                  previous_attempts: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """Create a repair plan based on bug report"""
        
        logger.info("Creating repair plan")
        
        # Validate bug report
        if not bug_report.get('bugs'):
            logger.warning("No bugs in report, creating null plan")
            return self._create_null_plan()
        
        # Build prompt
        prompt = self._build_planning_prompt(bug_report, repo_context, previous_attempts)
        
        try:
            plan = self.client.generate_json(prompt, self.SYSTEM_PROMPT)
            
            # Validate and enrich plan
            plan = self._validate_plan(plan, bug_report)
            
            logger.info(f"Plan created: {plan['strategy']} (risk: {plan['risk_level']})")
            return plan
            
        except Exception as e:
            logger.error(f"Planning failed: {e}")
            # Return conservative fallback plan
            return self._create_fallback_plan(bug_report)
    
    def update_plan_with_feedback(self, 
                                    current_plan: Dict[str, Any],
                                    feedback: Dict[str, Any]) -> Dict[str, Any]:
        """Update plan based on critic feedback"""
    
        logger.info("Updating plan with feedback")
    
    # Ensure current_plan has required fields
        if not isinstance(current_plan, dict) or 'strategy' not in current_plan:
            logger.warning("Invalid current plan, creating new fallback plan")
            return self._create_fallback_plan({"bugs": []})
    
        prompt = f"""The current repair plan failed. Update it based on the feedback.

    CURRENT PLAN:
    {json.dumps(current_plan, indent=2)}

    FEEDBACK:
    {json.dumps(feedback, indent=2)}

    Create an updated plan that addresses the feedback while maintaining minimal changes.
    Try a different strategy if the current one is not working."""
    
        try:
            updated_plan = self.client.generate_json(prompt, self.SYSTEM_PROMPT)
        
            # Validate the updated plan
            if not isinstance(updated_plan, dict):
                logger.warning("Updated plan is not a dict, trying next strategy")
                return self._try_next_strategy(current_plan)
        
        # Merge with current plan to preserve required fields
            merged_plan = {**current_plan, **updated_plan}
            return self._validate_plan(merged_plan, {"bugs": []})
        
        except Exception as e:
            logger.error(f"Plan update failed: {e}")
            # Try next strategy in priority list
            return self._try_next_strategy(current_plan)
    
    def _validate_plan(self, plan: Dict[str, Any], bug_report: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and enrich plan with defaults"""
        
        if not isinstance(plan, dict):
            logger.warning("Plan is not a dict, using fallback")
            return self._create_fallback_plan(bug_report)
        
        # Get first bug for context
        first_bug = bug_report.get('bugs', [{}])[0] if bug_report.get('bugs') else {}
        
        # Required fields with defaults
        defaults = {
            "strategy": plan.get('strategy', 'one_line_fix'),
            "target_function": plan.get('target_function', 'unknown'),
            "target_file": plan.get('target_file') or first_bug.get('file', 'unknown'),
            "line_range": plan.get('line_range', [
                first_bug.get('line_start', 0),
                first_bug.get('line_end', 0)
            ]),
            "issue_description": plan.get('issue_description') or first_bug.get('symptom', 'Unknown issue'),
            "fix_approach": plan.get('fix_approach', 'Manual review needed'),
            "tests_needed": plan.get('tests_needed', []),
            "risk_level": plan.get('risk_level', 'MEDIUM'),
            "confidence": min(plan.get('confidence', 0.5), bug_report.get('confidence', 0.5)),
            "timeout_secs": plan.get('timeout_secs', 30),
            "dependencies": plan.get('dependencies', []),
            "rollback_steps": plan.get('rollback_steps', []),
        }
        
        # Validate target_file exists
        if defaults['target_file'] == 'unknown' or not defaults['target_file']:
            logger.error("No valid target file in plan")
            if first_bug.get('file'):
                defaults['target_file'] = first_bug.get('file')
            else:
                defaults['target_file'] = 'tests/sample_buggy_code.py'
        
        # Add default rollback if missing
        if not defaults['rollback_steps']:
            defaults['rollback_steps'] = [f"git checkout HEAD -- {defaults['target_file']}"]
        
        return defaults
    
    def _create_fallback_plan(self, bug_report: Dict[str, Any]) -> Dict[str, Any]:
        """Create a conservative fallback plan"""
        
        first_bug = bug_report.get('bugs', [{}])[0] if bug_report.get('bugs') else {}
        
        target_file = first_bug.get('file', 'tests/sample_buggy_code.py')
        
        return {
            "strategy": "one_line_fix",
            "target_function": "unknown",
            "target_file": target_file,
            "line_range": [first_bug.get('line_start', 0), first_bug.get('line_end', 0)],
            "issue_description": first_bug.get('symptom', 'Unknown issue'),
            "fix_approach": first_bug.get('suggested_fix', 'Manual review needed'),
            "tests_needed": [],
            "risk_level": "HIGH",
            "confidence": 0.3,
            "timeout_secs": 30,
            "dependencies": [],
            "rollback_steps": [f"git checkout HEAD -- {target_file}"]
        }
    
    def _create_null_plan(self) -> Dict[str, Any]:
        """Create null plan when no bugs found"""
        return {
            "strategy": "none",
            "target_file": None,
            "target_function": None,
            "line_range": [0, 0],
            "issue_description": "No bugs found",
            "fix_approach": "No action needed",
            "tests_needed": [],
            "risk_level": "LOW",
            "confidence": 1.0,
            "timeout_secs": 0,
            "dependencies": [],
            "rollback_steps": []
        }
    
    def _build_planning_prompt(self, 
                                bug_report: Dict[str, Any],
                                repo_context: Dict[str, Any],
                                previous_attempts: Optional[List[Dict[str, Any]]] = None) -> str:
        """Build prompt for planning"""
        
        bugs_summary = "\n".join([
            f"Bug {i+1}: {bug['symptom']} at {bug['file']}:{bug['line_start']}-{bug['line_end']} (severity: {bug['severity']})"
            for i, bug in enumerate(bug_report.get('bugs', [])[:5])
        ])
        
        previous_summary = ""
        if previous_attempts:
            previous_summary = "\n\nPREVIOUS FAILED ATTEMPTS:\n" + "\n".join([
                f"- {att['strategy']}: {att.get('failure_reason', 'unknown')}"
                for att in previous_attempts[-3:]  # Last 3 attempts
            ])
        
        return f"""Create a repair plan for the following bugs.

BUG REPORT:
{bugs_summary}

Overall Confidence: {bug_report.get('confidence', 0.0)}

REPOSITORY CONTEXT:
Project Type: {repo_context.get('project_type', 'unknown')}
Language: {repo_context.get('language', 'Python')}
Test Framework: {repo_context.get('test_framework', 'pytest')}
Dependencies: {', '.join(repo_context.get('dependencies', [])[:10])}
{previous_summary}

Create a minimal, safe repair plan. Prefer simpler strategies (one-line fixes) over complex refactoring.
"""
    
    def _try_next_strategy(self, current_plan: Dict[str, Any]) -> Dict[str, Any]:
        """Try the next strategy in priority list"""
        
        current_strategy = current_plan.get('strategy', 'one_line_fix')
        
        try:
            current_idx = self.strategy_priority.index(current_strategy)
            if current_idx < len(self.strategy_priority) - 1:
                next_strategy = self.strategy_priority[current_idx + 1]
            else:
                next_strategy = "refactor"
        except ValueError:
            next_strategy = "one_line_fix"
        
        current_plan['strategy'] = next_strategy
        current_plan['confidence'] *= 0.8  # Reduce confidence
        
        logger.info(f"Trying next strategy: {next_strategy}")
        return current_plan