#tools/stewards_map.py
import os
import ast
import fnmatch
import time

# Load .gitignore patterns from project root
def load_gitignore(root_dir):
    ignore_patterns = [".git", "*.pyc", "__pycache__"]  # Defaults
    gitignore_path = os.path.join(root_dir, ".gitignore")
    try:
        with open(gitignore_path, "r") as f:
            ignore_patterns.extend(line.strip() for line in f if line.strip() and not line.startswith("#"))
    except FileNotFoundError:
        pass
    return ignore_patterns

# Check if a path matches .gitignore patterns
def is_ignored(path, ignore_patterns):
    for pattern in ignore_patterns:
        if fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(os.path.basename(path), pattern):
            return True
    return False

# Extract functions and key actions from a Python file
def parse_file(file_path):
    try:
        with open(file_path, "r") as f:
            tree = ast.parse(f.read())
        funcs = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
        calls = [node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and hasattr(node.func, "id")]
        sunshine = "sunshine" in calls  # Adjust if your LLM call has a specific name
        return {"functions": funcs, "sunshine": sunshine}
    except (SyntaxError, FileNotFoundError):
        return {"functions": [], "sunshine": False}

# Build the tree from the project root
def build_stewards_map(root_dir):
    ignore_patterns = load_gitignore(root_dir)
    tree = {"root": os.path.basename(root_dir), "files": {}}
    
    for dirpath, _, filenames in os.walk(root_dir):
        if is_ignored(dirpath, ignore_patterns):
            continue
        for filename in filenames:
            if filename.endswith(".py") and not is_ignored(filename, ignore_patterns):
                file_path = os.path.join(dirpath, filename)
                rel_path = os.path.relpath(file_path, root_dir)
                tree["files"][rel_path] = parse_file(file_path)
    
    return tree

# Visualize and save the tree
def visualize_and_save_tree(tree, output_dir="tools/maps"):
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(output_dir, f"map_{timestamp}.txt")
    os.makedirs(output_dir, exist_ok=True)
    
    tree_str = f"{tree['root']}/\n"
    files = sorted(tree["files"].items())
    for i, (path, details) in enumerate(files):
        prefix = "└──" if i == len(files) - 1 else "├──"
        tree_str += f"{prefix} {path}\n"
        funcs = details["functions"]
        sunshine = details["sunshine"]
        for j, func in enumerate(funcs):
            func_prefix = "    └──" if j == len(funcs) - 1 and not sunshine else "    ├──"
            tree_str += f"{func_prefix} {func}()\n"
        if sunshine:
            tree_str += "    └── sunshine()  # LLM API call\n"
    
    print(tree_str.strip())
    with open(output_file, "w") as f:
        f.write(tree_str)
    return tree_str

# Main function
def get_stewards_map():
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    tree = build_stewards_map(root_dir)
    tree_str = visualize_and_save_tree(tree)
    return tree

if __name__ == "__main__":
    get_stewards_map()