#!/usr/bin/env python3
"""
Complete end-to-end test of healing system
Works without Ollama using mocks
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

console = Console()

def test_complete_healing():
    """Test complete healing flow"""
    
    console.print(Panel("🧪 Testing Complete Healing Flow", style="bold cyan"))
    
    # Setup
    from tests.run_demo import setup_demo_environment
    setup_demo_environment()
    
    from pipelines.self_heal_loop import SelfHealingPipeline
    from utils.config import load_config
    
    config = load_config()
    pipeline = SelfHealingPipeline(config)
    
    console.print("[green]✓[/green] Pipeline initialized")
    
    # Test healing
    console.print("\n[bold]Healing tests/sample_buggy_code.py...[/bold]")
    
    result = pipeline.heal(
        target_file='tests/sample_buggy_code.py',
        repo_path='.'
    )
    
    console.print(f"\n[bold]Result:[/bold] {result['status']}")
    
    if result['status'] == 'SUCCESS':
        console.print(Panel("✅ HEALING SUCCESSFUL!", style="bold green"))
        
        # Show patch
        if 'patch' in result.get('details', {}):
            patch_text = result['details']['patch'].get('patch', '')
            console.print("\n[bold]Generated Patch:[/bold]")
            syntax = Syntax(patch_text, "diff", theme="monokai")
            console.print(syntax)
    else:
        console.print(Panel(f"⚠️  Status: {result['status']}", style="bold yellow"))
        
        # Show error details
        if 'details' in result:
            console.print("\n[bold]Details:[/bold]")
            import json
            console.print(json.dumps(result['details'], indent=2))
    
    return result['status'] == 'SUCCESS'

if __name__ == '__main__':
    success = test_complete_healing()
    sys.exit(0 if success else 1)