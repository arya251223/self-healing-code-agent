#!/usr/bin/env python3
"""
Simplified healing test that generates its own tests
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax
import json

console = Console()

def test_simple_healing():
    """Test healing with test generation"""
    
    console.print(Panel("🧪 Simple Healing Test", style="bold cyan"))
    
    # Force mock mode
    from tests.run_demo import setup_demo_environment
    setup_demo_environment()
    
    # Now import pipeline
    from pipelines.self_heal_loop import SelfHealingPipeline
    from utils.config import load_config
    
    config = load_config()
    
    # Force lower timeouts for testing
    config['models']['mistral']['timeout'] = 5
    config['models']['codellama']['timeout'] = 5
    config['models']['starcoder']['timeout'] = 5
    
    pipeline = SelfHealingPipeline(config)
    
    console.print("[green]✓[/green] Pipeline initialized\n")
    
    # Test healing
    console.print("[bold]Testing: tests/sample_buggy_code.py[/bold]\n")
    
    result = pipeline.heal(
        target_file='tests/sample_buggy_code.py',
        repo_path='.'
    )
    
    # Show result
    console.print(f"\n[bold]Status:[/bold] {result['status']}\n")
    
    if result['status'] == 'SUCCESS':
        console.print(Panel("✅ SUCCESS!", style="bold green"))
        
        details = result.get('details', {})
        
        # Show patch
        if 'patch' in details:
            console.print("\n[bold cyan]Generated Patch:[/bold cyan]")
            patch_text = details['patch'].get('patch', '')
            if patch_text:
                syntax = Syntax(patch_text, "diff", theme="monokai", line_numbers=False)
                console.print(syntax)
            
            # Show metadata
            metadata = details['patch'].get('metadata', {})
            console.print(f"\n[cyan]Lines changed:[/cyan] {metadata.get('lines_changed', 0)}")
            console.print(f"[cyan]Strategy:[/cyan] {details['patch'].get('strategy', 'unknown')}")
            console.print(f"[cyan]Confidence:[/cyan] {details['patch'].get('confidence', 0)*100:.1f}%")
        
        return True
        
    elif result['status'] == 'NO_BUGS_FOUND':
        console.print(Panel("ℹ️  No bugs found", style="bold blue"))
        return True
        
    else:
        console.print(Panel(f"⚠️  {result['status']}", style="bold yellow"))
        
        # Show details
        if 'details' in result:
            console.print("\n[bold]Details:[/bold]")
            details_str = json.dumps(result['details'], indent=2)
            # Truncate if too long
            if len(details_str) > 500:
                details_str = details_str[:500] + "\n... (truncated)"
            console.print(details_str)
        
        return False

if __name__ == '__main__':
    success = test_simple_healing()
    
    console.print("\n" + "="*60)
    if success:
        console.print(Panel("✅ [bold green]Test Passed![/bold green]", style="green"))
        sys.exit(0)
    else:
        console.print(Panel("❌ [bold red]Test Failed[/bold red]", style="red"))
        sys.exit(1)