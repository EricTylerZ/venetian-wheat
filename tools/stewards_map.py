# tools/stewards_map.py
import os
import ast
import fnmatch
import time
from pathlib import Path

# Load .gitignore patterns
def load_gitignore(root_dir):
    """Load patterns from .gitignore and return a list of ignore patterns."""
    ignore_patterns = []
    gitignore_path = Path(root_dir) / ".gitignore"
    if gitignore_path.exists():
        with gitignore_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    ignore_patterns.append(line)
    return ignore_patterns

# Check if a path should be ignored
def is_ignored(path, ignore_patterns, root_dir):
    """Determine if a path matches any .gitignore pattern."""
    path = Path(path)
    rel_path = path.relative_to(root_dir).as_posix()
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

# Parse a Python file for functions
def parse_file(file_path, log_file, include_params=True, include_descriptions=False):
    """Parse a Python file and return a list of functions with optional parameters and descriptions."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
        functions = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                name = node.name
                if include_params:
                    params = ', '.join(arg.arg for arg in node.args.args)
                    func_str = f"{name}({params})"
                else:
                    func_str = f"{name}()"
                if include_descriptions:
                    doc = ast.get_docstring(node)
                    if doc:
                        functions.append(f"{func_str} - {doc.strip().splitlines()[0]}")
                    else:
                        functions.append(func_str)
                else:
                    functions.append(func_str)
        return {"functions": functions}
    except (SyntaxError, UnicodeDecodeError) as e:
        with log_file.open("a", encoding="utf-8") as log:
            log.write(f"Error parsing {file_path}: {e}\n")
        return {"functions": []}

# Build the project tree, including config.json if present
def build_stewards_map(root_dir, log_file, include_params=True, include_descriptions=False):
    """Build a tree of Python files and include config.json if it exists in the root."""
    ignore_patterns = load_gitignore(root_dir)
    tree = {"root": os.path.basename(root_dir), "files": {}}
    
    # Check for config.json in root
    config_path = Path(root_dir) / "config.json"
    if config_path.exists():
        tree["files"]["config.json"] = {"note": "Configuration file"}
    
    for dirpath, _, filenames in os.walk(root_dir):
        if is_ignored(dirpath, ignore_patterns, root_dir):
            continue
        for filename in filenames:
            if filename.endswith(".py"):
                file_path = os.path.join(dirpath, filename)
                if not is_ignored(file_path, ignore_patterns, root_dir):
                    rel_path = Path(file_path).relative_to(root_dir).as_posix()
                    tree["files"][rel_path] = parse_file(file_path, log_file, include_params, include_descriptions)
    return tree

# Visualize and save the tree
def visualize_and_save_tree(tree, output_dir="tools/maps"):
    """Save the tree to a timestamped file with a concise header."""
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_file = Path(output_dir) / f"stewards_map_{timestamp}.txt"
    output_file.parent.mkdir(exist_ok=True)
    
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
        if "note" in details:
            tree_str += f"{prefix} {path} - {details['note']}\n"
        else:
            tree_str += f"{prefix} {path}\n"
            functions = details.get("functions", [])
            for j, func in enumerate(functions):
                func_prefix = "    └──" if j == len(functions) - 1 else "    ├──"
                tree_str += f"{func_prefix} {func}\n"
    
    with output_file.open("w", encoding="utf-8") as f:
        f.write(tree_str)
    
    print(f"Map saved to {output_file}")
    return tree_str

# New helper function to get the map as a string
def get_map_as_string(include_params=True, include_descriptions=False):
    """Generate the stewards map and return it as a formatted string."""
    root_dir = Path(__file__).parent.parent  # Two levels up from tools/
    log_file = root_dir / "tools" / "maps" / "errors.log"
    log_file.parent.mkdir(exist_ok=True)
    tree = build_stewards_map(root_dir, log_file, include_params, include_descriptions)
    
    # Format the tree into a string
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
        if "note" in details:
            tree_str += f"{prefix} {path} - {details['note']}\n"
        else:
            tree_str += f"{prefix} {path}\n"
            functions = details.get("functions", [])
            for j, func in enumerate(functions):
                func_prefix = "    └──" if j == len(functions) - 1 else "    ├──"
                tree_str += f"{func_prefix} {func}\n"
    
    return tree_str

# Main function
def get_stewards_map(include_params=True, include_descriptions=False):
    """Generate and save the stewards map."""
    root_dir = Path(__file__).parent.parent  # Two levels up from tools/
    log_file = root_dir / "tools" / "maps" / "errors.log"
    log_file.parent.mkdir(exist_ok=True)
    tree = build_stewards_map(root_dir, log_file, include_params, include_descriptions)
    visualize_and_save_tree(tree)
    return tree

if __name__ == "__main__":
    get_stewards_map(include_params=True, include_descriptions=True)