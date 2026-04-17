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
        self.blacklisted_paths = set()
        self.project_root = Path(os.getcwd())

    def on_mount(self) -> None:
        """Load initial whitelist when mounted."""
        self.whitelisted_paths, self.blacklisted_paths = load_whitelist(self.project_root)
        
        # If the user previously selected Option 1 (All Public), it saved a "." wildcard.
        # We must discard it so the interactive engine works, but we also must visually 
        # translate that wildcard into explicit selections so the UI starts completely Green!
        if "." in self.whitelisted_paths or "" in self.whitelisted_paths:
            self.whitelisted_paths.discard(".")
            self.whitelisted_paths.discard("")
            
            ignore_dirs = {".git", "node_modules", ".venv", "venv", "__pycache__"}
            try:
                for entry in self.project_root.iterdir():
                    if entry.name not in ignore_dirs:
                        self.whitelisted_paths.add(entry.name)
            except PermissionError:
                pass

    def on_key(self, event: Key) -> None:
        """Intercept spacebar to only toggle whitelist, and stop it from expanding."""
        if event.key == "space":
            self.app.action_toggle_whitelist()
            event.prevent_default()
            event.stop()

    def is_path_public(self, p: str) -> bool:
        """Evaluates explicitly resolving the dual Allow/Deny List rules."""
        is_safe = False
        p_norm = p.replace("\\", "/")
        
        for allowed in self.whitelisted_paths:
            allowed_norm = allowed.replace("\\", "/")
            if p_norm == allowed_norm or p_norm.startswith(f"{allowed_norm}/"):
                is_safe = True
                break
                
        for denied in self.blacklisted_paths:
            denied_norm = denied.replace("\\", "/")
            if p_norm == denied_norm or p_norm.startswith(f"{denied_norm}/"):
                is_safe = False
                break
                
        return is_safe

    def render_label(self, node: TreeNode, base_style, style):
        """Format the node text with its status."""
        label = super().render_label(node, base_style, style).copy()
        
        path = str(node.data) if node.data else ""
        rel_path = os.path.relpath(path, self.project_root) if path else ""
        
        if getattr(node, "is_root", False) or not path:
            return label
            
        status = "  [🟢 PUBLIC]" if self.is_path_public(rel_path) else "  [🔴 PRIVATE]"
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
        rel_path_norm = rel_path.replace("\\", "/")
        
        currently_public = tree.is_path_public(rel_path)
        
        if currently_public:
            # Transition to Private (Inject into Deny List)
            tree.whitelisted_paths.discard(rel_path)
            tree.blacklisted_paths.add(rel_path)
            
            # Recursively flush old descendant allow-rules to cleanly inherit the new block
            for x in list(tree.whitelisted_paths):
                if x.replace("\\", "/").startswith(f"{rel_path_norm}/"):
                    tree.whitelisted_paths.discard(x)
        else:
            # Transition to Public (Inject into Allow List)
            tree.blacklisted_paths.discard(rel_path)
            tree.whitelisted_paths.add(rel_path)
            
            # Recursively flush old descendant block-rules to cleanly inherit the new allowance
            for x in list(tree.blacklisted_paths):
                if x.replace("\\", "/").startswith(f"{rel_path_norm}/"):
                    tree.blacklisted_paths.discard(x)
                    
        # Visually refresh the exact node and all nested descendants
        def refresh_descendants(target_node: TreeNode):
            target_node.refresh()
            for child in target_node.children:
                refresh_descendants(child)
                
        refresh_descendants(node)

    def action_save_and_exit(self) -> None:
        """Save the current whitelist and exit."""
        tree = self.query_one(DirectoryTree)
        save_whitelist(self.project_root, tree.whitelisted_paths, tree.blacklisted_paths)
        self.exit(message="Whitelist saved successfully.")

if __name__ == "__main__":
    app = GateKeeperTUI()
    app.run()
