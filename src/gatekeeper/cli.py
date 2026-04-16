import typer
from rich.console import Console

console = Console()
app = typer.Typer(help="GateKeeper CLI - Zero-Trust Pre-Publish Firewall")

@app.command("init")
def init():
    """
    Initialize GateKeeper in the current project.
    """
    import os
    from pathlib import Path
    from gatekeeper.context import analyze_context
    from gatekeeper.tui import GateKeeperTUI
    from gatekeeper.config import GATEKEEPER_CONFIG_FILE, save_whitelist
    
    console.print("[bold green]Analyzing context...[/bold green]")
    project_root = Path(os.getcwd())
    context_data = analyze_context(project_root)
    
    if context_data["is_permanently_locked"]:
        console.print("[bold red]ERROR: This project is permanently locked (package.json has 'private': true). Publishing is forbidden.[/bold red]")
        raise typer.Exit(code=1)
        
    console.print(f"[cyan]Found {len(context_data['ignored_patterns'])} ignore patterns.[/cyan]")
    
    config_path = project_root / GATEKEEPER_CONFIG_FILE
    
    console.print("\n[bold yellow]GateKeeper Initialization[/bold yellow]")
    console.print("How would you like to configure this project?")
    console.print("  [1] [bold green]Open-Source[/bold green] (Make all files Public)")
    console.print("  [2] [bold red]Private App[/bold red] (Make all files Private)")
    console.print("  [3] [bold cyan]Mixed[/bold cyan] (Selective Publishing - opens UI)")
    
    choice = typer.prompt("Choose an option (1/2/3)", type=int)
    
    if choice == 1:
        save_whitelist(project_root, {"."}) # "." means the root directory, making everything public
        console.print("\n[bold green]✅ Project marked as Open-Source (All Public).[/bold green]")
        return
    elif choice == 2:
        save_whitelist(project_root, set()) # Empty set means nothing is public
        console.print("\n[bold green]✅ Project marked as Private App (All Private).[/bold green]")
        return
    elif choice == 3:
        console.print("\n[dim]Proceeding to Selective Publishing...[/dim]")
    else:
        console.print("[bold red]Invalid option. Aborting.[/bold red]")
        raise typer.Exit(code=1)

    console.print("[bold green]Launching Interactive Whitelist UI...[/bold green]")
    
    ui = GateKeeperTUI()
    result = ui.run()
    if result:
        console.print(f"[bold blue]{result}[/bold blue]")

@app.command("install")
def install():
    """
    Installs the GateKeeper shims into your shell environment to automatically intercept publish commands.
    """
    from gatekeeper.installer import install_shims
    install_shims()

@app.command("check")
def check(command: str = typer.Argument(..., help="The command to check (e.g. npm-publish, git-push)")):
    """
    Intercept and evaluate a publish/push command.
    """
    import os
    from pathlib import Path
    from gatekeeper.evaluator import evaluate_payload
    from gatekeeper.shims import get_npm_publish_files, get_git_push_files
    
    console.print(f"[bold cyan]GateKeeper intercepting:[/bold cyan] {command}")
    project_root = Path(os.getcwd())
    
    outgoing_files = []
    if command == "npm-publish":
        console.print("[dim]Extracting npm tarball payload via dry-run...[/dim]")
        outgoing_files = get_npm_publish_files(project_root)
    elif command == "git-push":
        console.print("[dim]Analyzing git diff for outgoing commits...[/dim]")
        outgoing_files = get_git_push_files(project_root)
    else:
        console.print(f"[yellow]Unknown interception command: {command}[/yellow]")
        raise typer.Exit(code=1)
        
    if not evaluate_payload(project_root, outgoing_files, command):
        console.print(f"\n[bold red]❌ {command.upper()} ABORTED BY GATEKEEPER.[/bold red]")
        raise typer.Exit(code=1)
        
    console.print(f"\n[bold green]✅ {command.upper()} IS SAFE TO PROCEED (Handing back to actual process).[/bold green]")

if __name__ == "__main__":
    app()
