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

    def render_label(self, node: TreeNode, base_style, style):
        """Format the node text with its status."""
        label = super().render_label(node, base_style, style).copy()
        
        path = str(node.data) if node.data else ""
        rel_path = os.path.relpath(path, self.project_root) if path else ""
        
        if getattr(node, "is_root", False) or not path:
            return label
            
        def is_path_public(p: str) -> bool:
            if p in self.whitelisted_paths: return True
            for parent in Path(p).parents:
                if str(parent).replace("\\", "/") in [x.replace("\\", "/") for x in self.whitelisted_paths]:
                    return True
            return False
            
        status = "  [🟢 PUBLIC]" if is_path_public(rel_path) else "  [🔴 PRIVATE]"
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
        
        # Prevent UI desync: A child cannot be toggled to Private if the parent folder is explicitly Public!
        is_parent_public = False
        for parent in Path(rel_path).parents:
            if str(parent).replace("\\", "/") in [x.replace("\\", "/") for x in tree.whitelisted_paths]:
                is_parent_public = True
                break
                
        if is_parent_public:
            self.bell()
            return
        
        # Determine if we are making it public or private based on the current state
        is_now_public = rel_path not in tree.whitelisted_paths
        
        # Recursive function to update the targeted node and all nested children
        def update_node_and_descendants(target_node: TreeNode, make_public: bool):
            p = target_node.data
            if not p:
                return
                
            r_path = os.path.relpath(p, self.project_root)
            if make_public:
                tree.whitelisted_paths.add(r_path)
            else:
                tree.whitelisted_paths.discard(r_path)
                
            target_node.refresh()
            
            # Recurse through children
            for child in target_node.children:
                update_node_and_descendants(child, make_public)
                
        # Apply the toggle to this node and everything inside it
        update_node_and_descendants(node, is_now_public)

    def action_save_and_exit(self) -> None:
        """Save the current whitelist and exit."""
        tree = self.query_one(DirectoryTree)
        save_whitelist(self.project_root, tree.whitelisted_paths)
        self.exit(message="Whitelist saved successfully.")

if __name__ == "__main__":
    app = GateKeeperTUI()
    app.run()
