import json
from typing import Dict, Any, List, Optional
from models.load_mistral import MistralClient
from services.static_analysis import StaticAnalyzer
from services.code_parser import CodeParser
from utils.logger import get_logger

logger = get_logger(__name__)

class AnalyzerAgent:
    """Agent responsible for analyzing code and identifying bugs"""
    
    SYSTEM_PROMPT = """You are AnalyzerAgent. Your job: examine provided code and/or test failure logs and produce a structured JSON bug_report. Use evidence (line numbers, stack traces). Avoid hallucination.

INSTRUCTIONS:
1. Provide list of issues with severity (HIGH/MEDIUM/LOW).
2. For each issue include file, line range, symptom, probable root cause, reproducible steps.
3. When given a stack trace, map it to file lines and functions.
4. Output only valid JSON with this structure:
{
  "bugs": [
    {
      "id": "unique_id",
      "file": "path/to/file.py",
      "line_start": 10,
      "line_end": 15,
      "severity": "HIGH|MEDIUM|LOW",
      "symptom": "description of the issue",
      "root_cause": "likely cause",
      "stack_trace": "optional stack trace",
      "suggested_fix": "brief suggestion"
    }
  ],
  "summary": "overall summary",
  "confidence": 0.0-1.0
}"""
    
    def __init__(self, mistral_client: MistralClient):
        self.client = mistral_client
        self.static_analyzer = StaticAnalyzer()
        self.code_parser = CodeParser()
        
    def analyze_file(self, file_path: str, content: Optional[str] = None) -> Dict[str, Any]:
        """Analyze a single file for bugs"""
        
        logger.info(f"Analyzing file: {file_path}")
        
        # Read file content if not provided
        if content is None:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            except Exception as e:
                logger.error(f"Could not read file {file_path}: {e}")
                return self._create_empty_bug_report()
        
        # Run static analysis first
        static_issues = self.static_analyzer.analyze(file_path, content)
        
        # Build prompt with code and static analysis results
        prompt = self._build_analysis_prompt(file_path, content, static_issues)
        
        # Get AI analysis
        try:
            bug_report = self.client.generate_json(prompt, self.SYSTEM_PROMPT)
            
            # Validate bug report structure
            bug_report = self._validate_bug_report(bug_report, file_path, static_issues)
            
            logger.info(f"Found {len(bug_report.get('bugs', []))} issues")
            return bug_report
            
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            # Return static analysis as structured fallback
            return self._create_fallback_report(file_path, static_issues)
    
    def analyze_trace(self, trace: str, files: Dict[str, str]) -> Dict[str, Any]:
        """Analyze stack trace and related files"""
        
        logger.info("Analyzing stack trace")
        
        # Parse stack trace to identify files and lines
        parsed_trace = self.code_parser.parse_trace(trace)
        
        # Load relevant code sections
        code_sections = {}
        for file_path in parsed_trace.get('files', []):
            if file_path in files:
                code_sections[file_path] = files[file_path]
        
        # Build prompt
        prompt = self._build_trace_analysis_prompt(trace, code_sections, parsed_trace)
        
        try:
            bug_report = self.client.generate_json(prompt, self.SYSTEM_PROMPT)
            bug_report = self._validate_bug_report(bug_report, parsed_trace.get('failed_file', 'unknown'), [])
            return bug_report
        except Exception as e:
            logger.error(f"Trace analysis failed: {e}")
            return self._create_trace_fallback_report(parsed_trace)
    
    def _validate_bug_report(self, report: Dict[str, Any], file_path: str, static_issues: list) -> Dict[str, Any]:
        """Validate and fix bug report structure"""
        
        if not isinstance(report, dict):
            return self._create_fallback_report(file_path, static_issues)
        
        # Ensure required fields
        if 'bugs' not in report or not isinstance(report['bugs'], list):
            report['bugs'] = []
        
        # Validate each bug
        validated_bugs = []
        for bug in report.get('bugs', []):
            if not isinstance(bug, dict):
                continue
            
            # Ensure all required fields
            validated_bug = {
                "id": bug.get('id', f"bug_{len(validated_bugs)}"),
                "file": bug.get('file', file_path),
                "line_start": bug.get('line_start', 0),
                "line_end": bug.get('line_end', 0),
                "severity": bug.get('severity', 'MEDIUM'),
                "symptom": bug.get('symptom', 'Unknown issue'),
                "root_cause": bug.get('root_cause', 'Analysis needed'),
                "suggested_fix": bug.get('suggested_fix', 'Manual review required'),
                "stack_trace": bug.get('stack_trace', '')
            }
            validated_bugs.append(validated_bug)
        
        report['bugs'] = validated_bugs
        
        # Ensure summary and confidence
        if 'summary' not in report:
            report['summary'] = f"Found {len(validated_bugs)} issues"
        
        if 'confidence' not in report:
            report['confidence'] = 0.5 if validated_bugs else 0.0
        
        return report
    
    def _create_fallback_report(self, file_path: str, static_issues: list) -> Dict[str, Any]:
        """Create fallback bug report from static analysis"""
        
        bugs = []
        for i, issue in enumerate(static_issues[:5]):  # Top 5 issues
            bugs.append({
                "id": f"static_{i}",
                "file": file_path,
                "line_start": issue.get('line', 0),
                "line_end": issue.get('line', 0),
                "severity": issue.get('severity', 'MEDIUM'),
                "symptom": issue.get('message', 'Static analysis issue'),
                "root_cause": f"Static analysis: {issue.get('type', 'unknown')}",
                "suggested_fix": "Review and fix manually",
                "stack_trace": ""
            })
        
        return {
            "bugs": bugs,
            "summary": f"Static analysis found {len(bugs)} issues (LLM unavailable)",
            "confidence": 0.6 if bugs else 0.0
        }
    
    def _create_empty_bug_report(self) -> Dict[str, Any]:
        """Create empty bug report"""
        return {
            "bugs": [],
            "summary": "Could not analyze file",
            "confidence": 0.0
        }
    
    def _create_trace_fallback_report(self, parsed_trace: Dict[str, Any]) -> Dict[str, Any]:
        """Create fallback report from parsed trace"""
        
        bug = {
            "id": "trace_001",
            "file": parsed_trace.get('failed_file', 'unknown'),
            "line_start": parsed_trace.get('failed_line', 0),
            "line_end": parsed_trace.get('failed_line', 0),
            "severity": "HIGH",
            "symptom": f"{parsed_trace.get('error_type', 'Error')}: {parsed_trace.get('error_message', 'unknown')}",
            "root_cause": "Error from stack trace (LLM unavailable)",
            "suggested_fix": "Review stack trace and fix error",
            "stack_trace": ""
        }
        
        return {
            "bugs": [bug],
            "summary": f"Trace analysis: {parsed_trace.get('error_type', 'Error')}",
            "confidence": 0.7
        }
    
    def _build_analysis_prompt(self, 
                                file_path: str, 
                                content: str, 
                                static_issues: List[Dict]) -> str:
        """Build prompt for file analysis"""
        
        static_summary = "\n".join([
            f"- Line {issue['line']}: {issue['message']} (severity: {issue['severity']})"
            for issue in static_issues[:10]  # Limit to top 10
        ])
        
        return f"""Analyze the following Python file for bugs and issues.

FILE: {file_path}

CODE:
{content}
STATIC ANALYSIS RESULTS:
{static_summary if static_summary else "No static analysis issues found."}

Provide a detailed bug report in JSON format identifying:

Syntax errors
Logic errors
Potential runtime errors
Code quality issues
Security vulnerabilities
Focus on actual bugs, not style preferences."""
    def _build_trace_analysis_prompt(self, 
                                    trace: str, 
                                    code_sections: Dict[str, str],
                                    parsed_trace: Dict[str, Any]) -> str:
        """Build prompt for trace analysis"""
    
        code_context = "\n\n".join([
            f"FILE: {path}\n```python\n{content}\n```"
            for path, content in code_sections.items()
        ])

        return f"""Analyze the following stack trace and identify the root cause
        STACK TRACE:

text

{trace}
RELEVANT CODE:
{code_context}

PARSED TRACE INFO:
Error Type: {parsed_trace.get('error_type', 'unknown')}
Error Message: {parsed_trace.get('error_message', 'unknown')}
Failed Line: {parsed_trace.get('failed_line', 'unknown')}

Provide a bug report in JSON format identifying:

The exact line(s) causing the failure
The root cause of the error
Suggested fix
Any related issues that might cause similar failures
"""