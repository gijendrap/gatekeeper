import os
from pathlib import Path
from textual.app import App, ComposeResult
from textual.events import Key
from textual.widgets import Header, Footer, Tree, Static
from textual.widgets._tree import TreeNode
from gatekeeper.config import load_config, save_config

class DirectoryTree(Tree):
    """A tree widget that displays a directory structure."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.public_paths = set()
        self.private_paths = set()
        self.project_root = Path(os.getcwd())

    def on_mount(self) -> None:
        """Load dual-state database when mounted."""
        state = load_config(self.project_root)
        self.public_paths = set(state.get("public", []))
        self.private_paths = set(state.get("private", []))
        
        # Purge any legacy wildcards
        self.public_paths.discard(".")
        self.public_paths.discard("")
        self.private_paths.discard(".")
        self.private_paths.discard("")

    def on_key(self, event: Key) -> None:
        """Intercept spacebar to only toggle whitelist, and stop it from expanding."""
        if event.key == "space":
            self.app.action_toggle_whitelist()
            event.prevent_default()
            event.stop()

    def render_label(self, node: TreeNode, base_style, style):
        """Format the node text with its strict exact status."""
        label = super().render_label(node, base_style, style).copy()
        
        path = str(node.data) if node.data else ""
        rel_path = Path(os.path.relpath(path, self.project_root)).as_posix() if path else ""
        
        if getattr(node, "is_root", False) or not path or rel_path == ".":
            return label
            
        if rel_path in self.public_paths:
            status = "  [🟢 PUBLIC]"
        elif rel_path in self.private_paths:
            status = "  [🔴 PRIVATE]"
        else:
            status = "  [⚪ UNASSIGNED]"
            
        label.append(status)
        return label

class GateKeeperTUI(App):
    """The GateKeeper Interactive Terminal UI."""
    
    CSS = """
    Screen {
        background: $surface;
    }
    #tree-view {
        height: 1fr;
        border: solid green;
    }
    #help-text {
        height: 3;
        dock: top;
        content-align: center middle;
        background: $primary-darken-2;
        color: $text;
        text-style: bold;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("enter", "toggle_node", "Expand/Collapse Folder"),
        ("space", "toggle_whitelist", "Toggle (Unassigned -> Public -> Private)"),
        ("s", "save_and_exit", "Save & Exit")
    ]

    def __init__(self):
        super().__init__()
        self.project_root = Path(os.getcwd())
        
    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header(show_clock=False)
        help_msg = (
            "Enter: Expand/Collapse | Space: Cycle Status | S: Save | Q: Quit\n"
            "All newborn files default to ⚪ UNASSIGNED. They will trigger firewall alarms until physically approved."
        )
        yield Static(help_msg, id="help-text")
        
        tree: DirectoryTree[Path] = DirectoryTree("Project Filesystem")
        tree.id = "tree-view"
        tree.root.expand() 
        self.populate_tree(tree.root, self.project_root)
        yield tree
        yield Footer()

    def populate_tree(self, node: TreeNode, path: Path) -> None:
        """Recursively populate the file tree, ignoring common large dirs."""
        ignore_dirs = {".git", "node_modules", ".venv", "venv", "__pycache__"}
        
        try:
            entries = sorted(path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
            for entry in entries:
                if entry.name in ignore_dirs:
                    continue
                if entry.is_dir():
                    child = node.add(entry.name, data=entry, expand=False)
                    self.populate_tree(child, entry)
                else:
                    node.add_leaf(entry.name, data=entry)
        except PermissionError:
            pass

    def action_toggle_whitelist(self) -> None:
        """Cycle the currently selected node's status."""
        tree = self.query_one(DirectoryTree)
        node = tree.cursor_node
        if not node or not node.data:
            return
            
        path = node.data
        rel_path = Path(os.path.relpath(path, self.project_root)).as_posix()
        
        is_public = rel_path in tree.public_paths
        is_private = rel_path in tree.private_paths
        
        if is_public:
            next_state = "private"
        elif is_private:
            next_state = "unassigned"
        else:
            next_state = "public"
        
        def apply_state(target_node: TreeNode):
            p = target_node.data
            if not p:
                return
                
            r = Path(os.path.relpath(p, self.project_root)).as_posix()
            
            if next_state == "public":
                tree.public_paths.add(r)
                tree.private_paths.discard(r)
            elif next_state == "private":
                tree.private_paths.add(r)
                tree.public_paths.discard(r)
            else:
                tree.public_paths.discard(r)
                tree.private_paths.discard(r)
                
            target_node.refresh()
            for child in target_node.children:
                apply_state(child)
                
        apply_state(node)

    def action_save_and_exit(self) -> None:
        """Save the dual-state config and exit."""
        tree = self.query_one(DirectoryTree)
        state = {
            "public": tree.public_paths,
            "private": tree.private_paths
        }
        save_config(self.project_root, state)
        self.exit(message="Whitelist configuration saved successfully.")

if __name__ == "__main__":
    app = GateKeeperTUI()
    app.run()
