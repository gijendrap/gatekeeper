import os
from pathlib import Path
from textual.app import App, ComposeResult
from textual.events import Key
from textual.widgets import Header, Footer, Tree, Static
from textual.widgets._tree import TreeNode
from gatekeeper.config import load_whitelist, save_whitelist

class DirectoryTree(Tree):
    """A tree widget that displays a directory structure."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.whitelisted_paths = set()
        self.project_root = Path(os.getcwd())

    def on_mount(self) -> None:
        """Load initial whitelist when mounted."""
        self.whitelisted_paths = load_whitelist(self.project_root)

    def on_key(self, event: Key) -> None:
        """Intercept spacebar to only toggle whitelist, and stop it from expanding."""
        if event.key == "space":
            self.app.action_toggle_whitelist()
            event.prevent_default()
            event.stop()

    def render_label(self, node: TreeNode, base_style, style):
        """Format the node text with its status."""
        label = super().render_label(node, base_style, style).copy()
        
        path = str(node.data) if node.data else ""
        rel_path = os.path.relpath(path, self.project_root) if path else ""
        
        if getattr(node, "is_root", False) or not path:
            return label
            
        status = "  [🟢 PUBLIC]" if rel_path in self.whitelisted_paths else "  [🔴 PRIVATE]"
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
        ("space", "toggle_whitelist", "Toggle Public/Private"),
        ("s", "save_and_exit", "Save & Exit")
    ]

    def __init__(self):
        super().__init__()
        self.project_root = Path(os.getcwd())
        
    def compose(self) -> ComposeResult:
        """Create child widgets for the app."""
        yield Header(show_clock=False)
        yield Static("Enter: Expand/Collapse | Space: Toggle Status | S: Save | Q: Quit\nAll files default to 🔴 PRIVATE. Explicitly mark allowed folders as 🟢 PUBLIC.", id="help-text")
        
        tree: DirectoryTree[Path] = DirectoryTree("Project Filesystem")
        tree.id = "tree-view"
        tree.root.expand() # Only expand the root folder itself so you see the top level domains
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
                    # explicitly declare expand=False so it shrinks/collapses folder by default
                    child = node.add(entry.name, data=entry, expand=False)
                    self.populate_tree(child, entry)
                else:
                    node.add_leaf(entry.name, data=entry)
        except PermissionError:
            pass

    def action_toggle_whitelist(self) -> None:
        """Toggle the currently selected node's status."""
        tree = self.query_one(DirectoryTree)
        node = tree.cursor_node
        if not node or not node.data:
            return
            
        path = node.data
        rel_path = os.path.relpath(path, self.project_root)
        
        # Toggle logic
        if rel_path in tree.whitelisted_paths:
            tree.whitelisted_paths.remove(rel_path)
            # Recursively remove children if a parent is un-whitelisted? To be complete.
        else:
            tree.whitelisted_paths.add(rel_path)
            
        # Refresh the node label
        node.refresh()

    def action_save_and_exit(self) -> None:
        """Save the current whitelist and exit."""
        tree = self.query_one(DirectoryTree)
        save_whitelist(self.project_root, tree.whitelisted_paths)
        self.exit(message="Whitelist saved successfully.")

if __name__ == "__main__":
    app = GateKeeperTUI()
    app.run()
