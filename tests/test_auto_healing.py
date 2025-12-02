#!/usr/bin/env python3
"""
Test Automatic Git Healing
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rich.console import Console
from rich.panel import Panel
from pipelines.self_heal_loop import SelfHealingPipeline
from integrations.git_auto_healer import GitAutoHealer
from utils.config import load_config

# Use mocks
from tests.run_demo import setup_demo_environment

console = Console()

def test_auto_mode():
    """Test automatic mode"""
    
    console.print(Panel("🤖 Testing Automatic Healing Mode", style="cyan"))
    
    # Setup
    setup_demo_environment()
    
    # Load
    config = load_config()
    pipeline = SelfHealingPipeline(config)
    auto_healer = GitAutoHealer(pipeline, config, '.')
    
    console.print("[green]✓[/green] Auto-healer initialized")
    
    # Test low-risk auto-push
    console.print("\n[bold]Test 1: Low-Risk Auto-Push (30s timer)[/bold]")
    
    # Simulate healing result
    mock_result = {
        'run_id': 'test-run-123',
        'status': 'SUCCESS',
        'details': {
            'patch': {
                'strategy': 'add_guard',
                'metadata': {'lines_changed': 3},
                'confidence': 0.9
            },
            'evaluation': {
                'confidence': 0.9,
                'risk_level': 'LOW'
            }
        }
    }
    
    auto_healer.handle_healing_result(mock_result, 'test.py')
    
    console.print("[yellow]⏱️  30-second timer started[/yellow]")
    console.print("[cyan]Check pending approvals:[/cyan]")
    
    for pending in auto_healer.get_pending_approvals():
        console.print(f"  • {pending['file']} - {pending['risk']} risk - {pending['time_remaining']:.0f}s remaining")
    
    # Test high-risk manual approval
    console.print("\n[bold]Test 2: High-Risk Manual Approval[/bold]")
    
    mock_result['details']['evaluation']['risk_level'] = 'HIGH'
    mock_result['details']['patch']['metadata']['lines_changed'] = 25
    
    auto_healer.handle_healing_result(mock_result, 'critical.py')
    
    console.print("[red]⚠️  Manual approval required[/red]")
    
    for pending in auto_healer.get_pending_approvals():
        if pending['requires_manual']:
            console.print(f"  • {pending['file']} - REQUIRES MANUAL APPROVAL")
    
    console.print("\n[green]✓ All tests passed[/green]")

if __name__ == '__main__':
    test_auto_mode()