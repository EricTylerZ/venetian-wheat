# tools/stewards_map.py
import os
import ast
import fnmatch
import time
from pathlib import Path

# Load .gitignore patterns from project root
def load_gitignore(root_dir):
    """Load patterns from .gitignore and return a list of ignore patterns."""
    ignore_patterns = []
    gitignore_path = Path(root_dir) / ".gitignore"
    if gitignore_path.exists():
        with gitignore_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):  # Skip empty lines and comments
                    ignore_patterns.append(line)
    return ignore_patterns

# Check if a path should be ignored based on .gitignore patterns
def is_ignored(path, ignore_patterns, root_dir):
    """Determine if a path matches any .gitignore pattern."""
    path = Path(path)
    rel_path = path.relative_to(root_dir).as_posix()  # Convert to relative POSIX path (/)
    
    for pattern in ignore_patterns:
        if pattern.endswith("/"):
            pattern = pattern.rstrip("/")
            if rel_path.startswith(pattern + "/") or rel_path == pattern:
                return True
        elif pattern.endswith("/*"):
            pattern = pattern.rstrip("/*")
            if rel_path.startswith(pattern + "/"):
                return True
        if fnmatch.fnmatch(rel_path, pattern) or fnmatch.fnmatch(path.name, pattern):
            return True
    return False

# Extract functions and key actions from a Python file
def parse_file(file_path, log_file, include_params=True):
    """Parse a Python file and return functions and LLM calls, logging errors if they occur."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        if include_params:
            funcs = [f"{node.name}({', '.join(arg.arg for arg in node.args.args)})" 
                     for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        else:
            funcs = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        calls = [node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and hasattr(node.func, "id")]
        sunshine = "sunshine" in calls  # Adjust if your LLM call has a specific name
        return {"functions": funcs, "sunshine": sunshine}
    except (SyntaxError, UnicodeDecodeError) as e:
        with log_file.open("a", encoding="utf-8") as log:
            log.write(f"Error parsing {file_path}: {e}\n")
        return {"functions": [], "sunshine": False}

# Build the tree from the project root
def build_stewards_map(root_dir, log_file, include_params=True):
    """Build a tree of Python files, respecting .gitignore patterns."""
    ignore_patterns = load_gitignore(root_dir)
    tree = {"root": os.path.basename(root_dir), "files": {}}
    
    for dirpath, _, filenames in os.walk(root_dir):
        if is_ignored(dirpath, ignore_patterns, root_dir):
            continue
        for filename in filenames:
            if filename.endswith(".py"):
                file_path = os.path.join(dirpath, filename)
                if not is_ignored(file_path, ignore_patterns, root_dir):
                    rel_path = Path(file_path).relative_to(root_dir).as_posix()
                    tree["files"][rel_path] = parse_file(file_path, log_file, include_params)
    
    return tree

# Visualize and save the tree to a file
def visualize_and_save_tree(tree, output_dir="tools/maps"):
    """Save the tree to a timestamped stewards_map_*.txt file with an explanation header."""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_file = Path(output_dir) / f"stewards_map_{timestamp}.txt"
    output_file.parent.mkdir(exist_ok=True)
    
    # Explanation header for the map
    header = """# Steward's Map Explanation
# This map provides a high-level overview of the project's Python files and their functions.
# It is intended for stewards (LLMs and humans) to understand the code structure and identify areas for improvement.
# Use this map to:
# - Add new features (e.g., expand self-growing logic in Venetian Wheat)
# - Optimize existing functions for better performance
# - Refactor code for improved readability or maintainability
# - Fix bugs or enhance functionality in the project files
"""
    
    tree_str = header + f"\n{tree['root']}/\n"
    files = sorted(tree["files"].items())
    for i, (path, details) in enumerate(files):
        prefix = "└──" if i == len(files) - 1 else "├──"
        tree_str += f"{prefix} {path}\n"
        funcs = details["functions"]
        sunshine = details["sunshine"]
        for j, func in enumerate(funcs):
            func_prefix = "    └──" if j == len(funcs) - 1 and not sunshine else "    ├──"
            tree_str += f"{func_prefix} {func}\n"
        if sunshine:
            tree_str += "    └── sunshine()  # LLM API call\n"
    
    with output_file.open("w", encoding="utf-8") as f:
        f.write(tree_str)
    
    print(f"Map saved to {output_file}")
    return tree_str

# Main function
def get_stewards_map(include_params=True):
    """Generate and save the stewards map, with optional parameter inclusion."""
    root_dir = Path(__file__).parent.parent  # Two levels up from tools/
    log_file = root_dir / "tools" / "maps" / "errors.log"
    log_file.parent.mkdir(exist_ok=True)  # Ensure log directory exists
    tree = build_stewards_map(root_dir, log_file, include_params)
    visualize_and_save_tree(tree)
    return tree

if __name__ == "__main__":
    get_stewards_map(include_params=True)