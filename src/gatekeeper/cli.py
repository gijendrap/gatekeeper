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
    
    gitignore_path = project_root / ".gitignore"
    if not gitignore_path.exists():
        console.print("[yellow]No .gitignore found! GateKeeper is auto-seeding standard dependency ignores...[/yellow]")
        with open(gitignore_path, "w", encoding="utf-8") as f:
            f.write("# GateKeeper Auto-Seeded Ignores\nvenv/\n.venv/\nnode_modules/\n__pycache__/\n.env\n*.pyc\ndist/\nbuild/\n.DS_Store\n")
        console.print("[bold green]✅ Protected repository from environment bloat![/bold green]")
        
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
        console.print("[bold yellow]💡 TIP:[/bold yellow] Maximize your terminal vertically to see the full interactive file tree clearly!")
        console.input("\nPress [bold cyan]\\[ENTER][/bold cyan] to launch the Interactive UI...")
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
    from gatekeeper.evaluator import evaluate_payload, check_bloat
    from gatekeeper.shims import get_npm_publish_files, get_git_push_files
    from gatekeeper.config import GATEKEEPER_CONFIG_FILE
    
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
        
    # Global Bloat Check (Runs even if GateKeeper isn't initialized!)
    bloat_res = check_bloat(project_root, outgoing_files, command)
    if bloat_res == -1:
        console.print(f"\n[bold red]❌ {command.upper()} ABORTED BY GATEKEEPER.[/bold red]")
        raise typer.Exit(code=1)
    elif bloat_res == 1:
        # If bloat was stripped, we must RE-ANALYZE the commit because files changed!
        if command == "npm-publish":
            outgoing_files = get_npm_publish_files(project_root)
        elif command == "git-push":
            outgoing_files = get_git_push_files(project_root)
    
    config_path = project_root / GATEKEEPER_CONFIG_FILE
    if not config_path.exists():
        console.print("\n[bold red]🚨 No GateKeeper Security Firewall detected in this repository![/bold red]")
        console.print("Do you want to:")
        console.print("  [1] [bold green]Initialize GateKeeper now[/bold green]")
        console.print("  [2] [bold yellow]Push Unprotected (Bypass Firewall)[/bold yellow]")
        console.print("  [3] [bold red]Abort Push[/bold red]")
        
        choice = typer.prompt("Choose an option (1/2/3)", type=int)
        if choice == 1:
            init()
            console.print("\n[bold cyan]GateKeeper intercepting:[/bold cyan] Resuming evaluation with new rules...")
        elif choice == 2:
            console.print("\n[bold yellow]⚠️ Proceeding with UNPROTECTED push...[/bold yellow]")
            console.print(f"\n[bold green]✅ {command.upper()} IS SAFE TO PROCEED (Handing back to actual process).[/bold green]")
            return
        else:
            console.print(f"\n[bold red]❌ {command.upper()} ABORTED BY GATEKEEPER.[/bold red]")
            raise typer.Exit(code=1)
        
    if not evaluate_payload(project_root, outgoing_files, command):
        console.print(f"\n[bold red]❌ {command.upper()} ABORTED BY GATEKEEPER.[/bold red]")
        raise typer.Exit(code=1)
        
    console.print(f"\n[bold green]✅ {command.upper()} IS SAFE TO PROCEED (Handing back to actual process).[/bold green]")

if __name__ == "__main__":
    app()
