#!/usr/bin/env python3
"""
Complete Demo/Test Script for Self-Healing Code Agent
NO API KEYS REQUIRED - Works completely offline!
"""

import os
import sys
import time
import json

# Add parent directory to path
import os
from typer import prompt
import yaml

def load_config():
    # Get absolute path to project root
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(root_dir, "config.yaml")

    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.syntax import Syntax

console = Console()

# Mock LLM responses for testing without real models
class MockLLMClient:
    """Mock LLM client for testing without Ollama"""
    
    def __init__(self, model_name):
        self.model_name = model_name
        console.print(f"[yellow]⚠️  Using Mock {model_name} (no Ollama needed)[/yellow]")
    
    def generate(self, prompt, system=None, temperature=None, max_tokens=None):
        """Generate mock response"""
        time.sleep(0.5)  # Simulate processing
        
        if "bug" in prompt.lower() or "analyze" in prompt.lower():
            return self._mock_bug_analysis()
        elif "plan" in prompt.lower() or "strategy" in prompt.lower():
            return self._mock_plan()
        elif "evaluate" in prompt.lower() or "critic" in prompt.lower():
            return self._mock_evaluation()
        else:
            return '{"result": "mock response"}'
    
    # Fix MockLLMClient.generate_json for planner
    def generate_json(self, prompt, system=None):
        """Generate mock JSON response"""
        time.sleep(0.5)
    
        if "bug" in prompt.lower() or "analyze" in prompt.lower():
            return {
                "bugs": [
                    {
                        "id": "bug_001",
                        "file": "tests/sample_buggy_code.py",
                        "line_start": 4,
                        "line_end": 6,
                        "severity": "HIGH",
                        "symptom": "ZeroDivisionError: division by zero",
                        "root_cause": "Missing zero check in divide_numbers function",
                        "suggested_fix": "Add check: if b == 0: raise ValueError('Cannot divide by zero')"
                    }
                ],
                "summary": "Found 1 critical bug",
                "confidence": 0.9
            }
        elif "plan" in prompt.lower() or "strategy" in prompt.lower():
            return {
                "strategy": "add_guard",
                "target_function": "divide_numbers",
                "target_file": "tests/sample_buggy_code.py",  # IMPORTANT!
                "line_range": [4, 6],
                "issue_description": "Missing zero division check",
                "fix_approach": "Add guard clause before division",
                "tests_needed": ["test_divide_by_zero"],
                "risk_level": "LOW",
                "confidence": 0.85,
                "timeout_secs": 20,
                "dependencies": [],
                "rollback_steps": ["git checkout HEAD -- tests/sample_buggy_code.py"]
            }
        elif "evaluate" in prompt.lower() or "critic" in prompt.lower():
            return {
                "verdict": "PASS",
                "confidence": 0.9,
                "rationale": "Patch correctly adds zero check, tests pass, minimal changes",
                "issues_found": [],
                "suggestions": [],
                "security_concerns": [],
                "test_coverage": 1.0,
                "should_auto_merge": True
            }
        else:
            return {"result": "mock"}
    # ... rest of the code
    
    def _mock_bug_analysis(self):
        return json.dumps({
            "bugs": [{
                "id": "bug_001",
                "file": "tests/sample_buggy_code.py",
                "line_start": 4,
                "severity": "HIGH",
                "symptom": "ZeroDivisionError"
            }]
        })
    
    def _mock_plan(self):
        return json.dumps({
            "strategy": "add_guard",
            "confidence": 0.85
        })
    
    def _mock_evaluation(self):
        return json.dumps({
            "verdict": "PASS",
            "confidence": 0.9
        })

class MockCodeLlamaClient(MockLLMClient):
    """Mock CodeLlama for patch generation"""
    
    def generate_patch(self, code_context, plan, system=None, temperature=None):
        """Generate mock patch"""
        time.sleep(0.8)
        
        return """--- a/tests/sample_buggy_code.py
+++ b/tests/sample_buggy_code.py
@@ -2,7 +2,10 @@
 
 def divide_numbers(a, b):
     \"\"\"Buggy division function - missing zero check\"\"\"
+    if b == 0:
+        raise ValueError("Cannot divide by zero")
     result = a / b
     return result
"""

class MockStarCoderClient(MockLLMClient):
    """Mock StarCoder for test generation"""
    
    def generate_tests(self, function_code, function_name, system=None):
        """Generate mock tests"""
        time.sleep(0.6)
        
        return """import pytest

def test_divide_numbers_basic():
    \"\"\"Test basic division\"\"\"
    from sample_buggy_code import divide_numbers
    assert divide_numbers(10, 2) == 5
    assert divide_numbers(20, 4) == 5

def test_divide_numbers_zero():
    \"\"\"Test division by zero\"\"\"
    from sample_buggy_code import divide_numbers
    with pytest.raises(ValueError, match="Cannot divide by zero"):
        divide_numbers(10, 0)

def test_divide_numbers_negative():
    \"\"\"Test negative numbers\"\"\"
    from sample_buggy_code import divide_numbers
    assert divide_numbers(-10, 2) == -5
"""

def setup_demo_environment():
    """Setup demo environment"""
    
    console.print(Panel.fit(
        "[bold cyan]🤖 Self-Healing Code Agent - DEMO MODE[/bold cyan]\n"
        "[yellow]Running in DEMO mode - No Ollama/API keys required![/yellow]",
        title="Welcome"
    ))
    
    # Create necessary directories
    os.makedirs('data/logs', exist_ok=True)
    os.makedirs('data/patches', exist_ok=True)
    os.makedirs('data/memory', exist_ok=True)
    
    console.print("[green]✓[/green] Created data directories")
    
    # Monkey patch model loaders to use mocks
    import models.load_mistral as mistral_module
    import models.load_codellama as codellama_module
    import models.load_starcoder as starcoder_module
    
    mistral_module.MistralClient = MockLLMClient
    codellama_module.CodeLlamaClient = MockCodeLlamaClient
    starcoder_module.StarCoderClient = MockStarCoderClient
    
    console.print("[green]✓[/green] Configured mock AI models")
    
    return True

def demo_basic_healing():
    """Demo 1: Basic healing of a simple bug"""
    
    console.print("\n" + "="*60)
    console.print(Panel("[bold]Demo 1: Basic Bug Healing[/bold]", style="cyan"))
    
    from pipelines.self_heal_loop import SelfHealingPipeline
    from utils.config import load_config
    
    # Load config
    config = load_config()
    
    # Initialize pipeline
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("Initializing pipeline...", total=None)
        pipeline = SelfHealingPipeline(config)
        progress.update(task, description="✓ Pipeline ready")
    
    # Show buggy code
    console.print("\n[bold]Buggy Code:[/bold]")
    with open('tests/sample_buggy_code.py', 'r') as f:
        code = f.read()
        syntax = Syntax(code[:300] + "...", "python", theme="monokai", line_numbers=True)
        console.print(syntax)
    
    # Run healing
    console.print("\n[bold yellow]Starting self-healing process...[/bold yellow]")
    
    result = pipeline.heal(
        target_file='tests/sample_buggy_code.py',
        repo_path='.'
    )
    
    # Display results
    console.print("\n[bold]Results:[/bold]")
    
    if result['status'] == 'SUCCESS':
        console.print(Panel("✅ [bold green]Healing Successful![/bold green]", style="green"))
        
        details = result.get('details', {})
        if 'patch' in details:
            console.print("\n[bold]Generated Patch:[/bold]")
            patch_text = details['patch'].get('patch', '')
            syntax = Syntax(patch_text, "diff", theme="monokai")
            console.print(syntax)
        
        # Show stats
        table = Table(title="Patch Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")
        
        metadata = details.get('patch', {}).get('metadata', {})
        table.add_row("Lines Changed", str(metadata.get('lines_changed', 0)))
        table.add_row("Strategy", details.get('patch', {}).get('strategy', 'N/A'))
        table.add_row("Confidence", f"{details.get('patch', {}).get('confidence', 0)*100:.1f}%")
        
        console.print(table)
    else:
        console.print(Panel(f"Status: {result['status']}", style="yellow"))
    
    return result

def demo_trace_analysis():
    """Demo 2: Analyze stack trace"""
    
    console.print("\n" + "="*60)
    console.print(Panel("[bold]Demo 2: Stack Trace Analysis[/bold]", style="cyan"))
    
    # Create sample stack trace
    stack_trace = """Traceback (most recent call last):
  File "tests/sample_buggy_code.py", line 4, in divide_numbers
    result = a / b
ZeroDivisionError: division by zero

The above exception was the direct cause of the following exception:

Traceback (most recent call last):
  File "test_app.py", line 10, in test_calculation
    result = divide_numbers(10, 0)
ZeroDivisionError: division by zero
"""
    
    console.print("[bold]Stack Trace:[/bold]")
    console.print(Panel(stack_trace, style="red"))
    
    from pipelines.self_heal_loop import SelfHealingPipeline
    from utils.config import load_config
    
    config = load_config()
    pipeline = SelfHealingPipeline(config)
    
    console.print("\n[bold yellow]Analyzing trace and healing...[/bold yellow]")
    
    result = pipeline.heal(
        stack_trace=stack_trace,
        repo_path='.'
    )
    
    console.print(Panel(f"✓ Analysis complete: {result['status']}", style="green"))
    
    return result

def demo_multi_file_awareness():
    """Demo 3: Multi-file dependency awareness"""
    
    console.print("\n" + "="*60)
    console.print(Panel("[bold]Demo 3: Multi-File Dependency Analysis[/bold]", style="cyan"))
    
    from services.dependency_analyzer import DependencyAnalyzer
    
    analyzer = DependencyAnalyzer()
    
    # Get all Python files
    import glob
    files = glob.glob('**/*.py', recursive=True)
    files = [f for f in files if 'venv' not in f and '__pycache__' not in f][:10]
    
    console.print(f"[bold]Analyzing {len(files)} files...[/bold]")
    
    # Build dependency graph
    graph = analyzer.build_dependency_graph(files)
    
    # Display graph
    if graph:
        table = Table(title="Dependency Graph")
        table.add_column("File", style="cyan")
        table.add_column("Dependencies", style="magenta")
        
        for file, deps in list(graph.items())[:5]:
            table.add_row(file, "\n".join(deps) if deps else "None")
        
        console.print(table)
    else:
        console.print("[yellow]No dependencies found[/yellow]")
    
    # Detect project type
    project_type = analyzer.detect_project_type('.')
    test_framework = analyzer.detect_test_framework('.')
    
    console.print(f"\n[bold]Project Type:[/bold] {project_type}")
    console.print(f"[bold]Test Framework:[/bold] {test_framework}")

def demo_learning_system():
    """Demo 4: Learning from past fixes"""
    
    console.print("\n" + "="*60)
    console.print(Panel("[bold]Demo 4: Self-Learning System[/bold]", style="cyan"))
    
    from services.learning_system import LearningSystem
    from utils.config import load_config
    
    config = load_config()
    learning = LearningSystem(config)
    
    # Simulate recording a successful fix
    bug_report = {
        "bugs": [{
            "symptom": "ZeroDivisionError",
            "root_cause": "Missing zero check",
            "file": "test.py"
        }]
    }
    
    result = {
        "patch": {
            "strategy": "add_guard",
            "confidence": 0.9
        }
    }
    
    console.print("[bold]Recording successful fix...[/bold]")
    learning.record_success(bug_report, result)
    console.print("[green]✓[/green] Fix recorded")
    
    # Search for similar bugs
    console.print("\n[bold]Searching for similar past fixes...[/bold]")
    similar = learning.find_similar_bugs(bug_report, limit=3)
    
    if similar:
        console.print(f"[green]Found {len(similar)} similar fixes[/green]")
        for i, fix in enumerate(similar, 1):
            console.print(f"{i}. Similarity: {fix.get('similarity', 0):.2f}")
    else:
        console.print("[yellow]No similar fixes found (database is empty)[/yellow]")
    
    # Get strategy success rate
    success_rate = learning.get_success_rate("add_guard")
    console.print(f"\n[bold]'add_guard' strategy success rate:[/bold] {success_rate*100:.1f}%")

def demo_web_interface():
    """Demo 5: Show web interface info"""
    
    console.print("\n" + "="*60)
    console.print(Panel("[bold]Demo 5: Web Interface[/bold]", style="cyan"))
    
    console.print("""
[bold cyan]Web Interface Features:[/bold cyan]

1. 📊 [bold]Dashboard[/bold]
   - Real-time healing statistics
   - Recent healing runs with status
   - Success/failure metrics

2. 🔍 [bold]Patch Review[/bold]
   - View generated patches with syntax highlighting
   - Approve or reject patches
   - See quality evaluation results

3. 🔔 [bold]Notifications[/bold]
   - Real-time notifications via WebSocket
   - Success/failure/escalation alerts
   - Action-required notifications

4. 🚀 [bold]Healing Trigger[/bold]
   - Upload files or paste stack traces
   - Configure repository path
   - Start healing with one click

[bold yellow]To start the web interface:[/bold yellow]
    python interface/api.py

Then open: http://localhost:8000
""")

def demo_statistics():
    """Show final statistics"""
    
    console.print("\n" + "="*60)
    console.print(Panel("[bold]Demo Summary & Statistics[/bold]", style="cyan"))
    
    from services.experiment_logger import ExperimentLogger
    from utils.config import load_config
    
    config = load_config()
    logger = ExperimentLogger(config)
    
    runs = logger.get_recent_runs(limit=100)
    
    if runs:
        table = Table(title="System Statistics")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="magenta")
        
        total = len(runs)
        successful = sum(1 for r in runs if r.get('result', {}).get('status') == 'SUCCESS')
        
        table.add_row("Total Runs", str(total))
        table.add_row("Successful", str(successful))
        table.add_row("Success Rate", f"{(successful/total*100):.1f}%")
        
        console.print(table)
    else:
        console.print("[yellow]No runs recorded yet[/yellow]")

def main():
    """Main demo runner"""
    
    try:
        # Setup
        setup_demo_environment()
        
        # Run demos
        console.print("\n[bold cyan]Running Demos...[/bold cyan]\n")
        
        # Demo 1: Basic healing
        demo_basic_healing()
        
        # Demo 2: Trace analysis
        demo_trace_analysis()
        
        # Demo 3: Multi-file
        demo_multi_file_awareness()
        
        # Demo 4: Learning
        demo_learning_system()
        
        # Demo 5: Web interface info
        demo_web_interface()
        
        # Final stats
        demo_statistics()
        
        # Success message
        console.print("\n" + "="*60)
        console.print(Panel.fit(
            "[bold green]✅ All Demos Completed Successfully![/bold green]\n\n"
            "[cyan]The Self-Healing Code Agent is working perfectly![/cyan]\n\n"
            "[yellow]Next Steps:[/yellow]\n"
            "1. Start web interface: python interface/api.py\n"
            "2. Try CLI: python interface/cli.py heal --help\n"
            "3. Install Ollama for real AI models\n"
            "4. Integrate with your CI/CD pipeline",
            title="🎉 Demo Complete"
        ))
        
    except Exception as e:
        console.print(f"\n[bold red]Error:[/bold red] {e}")
        import traceback
        console.print(traceback.format_exc())

if __name__ == '__main__':
    main()