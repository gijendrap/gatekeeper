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
    from gatekeeper.config import save_config
    
    console.print("[bold green]Analyzing context...[/bold green]")
    project_root = Path(os.getcwd())
    context_data = analyze_context(project_root)
    
    if context_data["is_permanently_locked"]:
        console.print("[bold red]ERROR: This project is permanently locked (package.json has 'private': true). Publishing is forbidden.[/bold red]")
        raise typer.Exit(code=1)
        
    console.print(f"[cyan]Found {len(context_data['ignored_patterns'])} ignore patterns.[/cyan]")
    
    config_path = project_root / ".gatekeeper.json"
    
    console.print("\n[bold yellow]GateKeeper Initialization[/bold yellow]")
    console.print("How would you like to configure this project?")
    console.print("  [1] [bold green]Open-Source[/bold green] (Make all files Public)")
    console.print("  [2] [bold red]Private App[/bold red] (Make all files Private)")
    console.print("  [3] [bold cyan]Mixed[/bold cyan] (Selective Publishing - opens UI)")
    
    choice = typer.prompt("Choose an option (1/2/3)", type=int)
    
    if choice == 1:
        all_files = set()
        for root, dirs, files in os.walk(project_root):
            if ".git" in root or "node_modules" in root or "__pycache__" in root:
                continue
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), project_root)
                all_files.add(Path(rel).as_posix())
        save_config(project_root, {"public": all_files, "private": set()})
        console.print("\n[bold green]✅ Project marked as Open-Source (All Current Files Public).[/bold green]")
        console.print("[yellow]Note: Any future files you create will trigger the firewall as UNASSIGNED![/yellow]")
        return
    elif choice == 2:
        all_files = set()
        for root, dirs, files in os.walk(project_root):
            if ".git" in root or "node_modules" in root or "__pycache__" in root:
                continue
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), project_root)
                all_files.add(Path(rel).as_posix())
        save_config(project_root, {"public": set(), "private": all_files})
        console.print("\n[bold green]✅ Project marked as Private App (All Current Files Private).[/bold green]")
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
