import click
import json
import time
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.syntax import Syntax

from pipelines.self_heal_loop import SelfHealingPipeline
from utils.config import load_config
from utils.logger import get_logger

console = Console()
logger = get_logger(__name__)

@click.group()
def cli():
    """Self-Healing Code Agent CLI"""
    pass

@cli.command()
@click.option('--file', '-f', help='Target file to analyze')
@click.option('--trace', '-t', help='Stack trace file')
@click.option('--repo', '-r', default='.', help='Repository path')
def heal(file, trace, repo):
    """Start self-healing process"""
    
    console.print(Panel.fit("🤖 Self-Healing Code Agent", style="bold magenta"))
    
    # Load config
    config = load_config()
    
    # Read trace if file provided
    stack_trace = None
    if trace:
        with open(trace, 'r') as f:
            stack_trace = f.read()
    
    # Initialize pipeline
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console
    ) as progress:
        
        task = progress.add_task("Initializing pipeline...", total=None)
        pipeline = SelfHealingPipeline(config)
        progress.update(task, completed=True)
        
        task = progress.add_task("Running self-healing...", total=None)
        result = pipeline.heal(
            target_file=file,
            stack_trace=stack_trace,
            repo_path=repo
        )
        progress.update(task, completed=True)
    
    # Display results
    console.print("\n")
    display_result(result)

@cli.command()
@click.option('--limit', '-l', default=10, help='Number of runs to show')
def history(limit):
    """Show healing history"""
    
    config = load_config()
    from services.experiment_logger import ExperimentLogger
    
    logger_service = ExperimentLogger(config)
    runs = logger_service.get_recent_runs(limit=limit)
    
    if not runs:
        console.print("[yellow]No healing runs found[/yellow]")
        return
    
    table = Table(title="Recent Healing Runs")
    table.add_column("Run ID", style="cyan")
    table.add_column("Status", style="magenta")
    table.add_column("Duration", style="green")
    table.add_column("Time", style="blue")
    
    for run in runs:
        run_id = run['run_id'][:8]
        status = run.get('result', {}).get('status', 'UNKNOWN')
        duration = f"{run.get('duration_seconds', 0):.2f}s"
        timestamp = run.get('start_time', 'N/A')
        
        table.add_row(run_id, status, duration, timestamp)
    
    console.print(table)

@cli.command()
@click.argument('run_id')
def show(run_id):
    """Show details of a specific run"""
    
    config = load_config()
    from services.experiment_logger import ExperimentLogger
    
    logger_service = ExperimentLogger(config)
    run = logger_service.get_run(run_id)
    
    if not run:
        console.print(f"[red]Run {run_id} not found[/red]")
        return
    
    console.print(Panel(json.dumps(run, indent=2), title=f"Run {run_id[:8]}"))

@cli.command()
def stats():
    """Show system statistics"""
    
    config = load_config()
    from services.experiment_logger import ExperimentLogger
    
    logger_service = ExperimentLogger(config)
    runs = logger_service.get_recent_runs(limit=100)
    
    total = len(runs)
    successful = sum(1 for r in runs if r.get('result', {}).get('status') == 'SUCCESS')
    failed = sum(1 for r in runs if r.get('result', {}).get('status') in ['FAILED', 'MAX_ATTEMPTS_REACHED'])
    escalated = sum(1 for r in runs if r.get('result', {}).get('status') == 'ESCALATED')
    
    table = Table(title="System Statistics")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="magenta")
    
    table.add_row("Total Runs", str(total))
    table.add_row("Successful", str(successful))
    table.add_row("Failed", str(failed))
    table.add_row("Escalated", str(escalated))
    
    if total > 0:
        success_rate = (successful / total) * 100
        table.add_row("Success Rate", f"{success_rate:.1f}%")
    
    console.print(table)

@cli.command()
@click.option('--repo', '-r', default='.', help='Repository path')
def auto(repo):
    """Start automatic healing mode"""
    
    console.print(Panel.fit("🤖 Starting Automatic Healing Mode", style="bold green"))
    
    config = load_config()
    
    from pipelines.self_heal_loop import SelfHealingPipeline
    from integrations.git_auto_healer import GitAutoHealer
    
    # Initialize
    pipeline = SelfHealingPipeline(config)
    auto_healer = GitAutoHealer(pipeline, config, repo)
    
    console.print("\n[green]✓[/green] Auto-healer initialized")
    console.print(f"[cyan]Watching:[/cyan] {repo}")
    console.print(f"[cyan]Low-risk timeout:[/cyan] {config['git_auto']['low_risk_timeout']}s")
    console.print("\n[yellow]Press Ctrl+C to stop[/yellow]\n")
    
    # Start
    auto_healer.start_auto_healing()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        console.print("\n\n[yellow]Stopping...[/yellow]")
        auto_healer.stop_auto_healing()
        console.print("[green]✓ Stopped[/green]")

@cli.command()
def hooks():
    """Install git hooks"""
    
    from integrations.install_git_hooks import install_hooks
    
    console.print("Installing git hooks...")
    
    if install_hooks():
        console.print("[green]✓ Git hooks installed[/green]")
        console.print("\nHooks installed:")
        console.print("  • pre-commit: Auto-scan before commit")
    else:
        console.print("[red]✗ Failed to install hooks[/red]")

def display_result(result):
    """Display healing result"""
    
    status = result.get('status', 'UNKNOWN')
    
    if status == 'SUCCESS':
        console.print(Panel("✅ Healing Successful!", style="bold green"))
        
        details = result.get('details', {})
        if 'patch' in details:
            patch_text = details['patch'].get('patch', '')
            syntax = Syntax(patch_text, "diff", theme="monokai")
            console.print(Panel(syntax, title="Generated Patch"))
        
        if details.get('requires_approval'):
            console.print("[yellow]⚠️  Manual approval required[/yellow]")
    
    elif status == 'ESCALATED':
        console.print(Panel("⚠️  Escalated for Manual Review", style="bold yellow"))
        reason = result.get('details', {}).get('reason', 'Unknown')
        console.print(f"Reason: {reason}")
    
    else:
        console.print(Panel(f"❌ Status: {status}", style="bold red"))
        console.print(json.dumps(result.get('details', {}), indent=2))

if __name__ == '__main__':
    cli()