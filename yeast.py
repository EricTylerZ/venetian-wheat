#yeast.py
"""
Yeast: A script to apply diff-like changes to files in the Venetian Wheat project.
Paste LLM-provided snippets (e.g., 'FILE: path/to/file\n- line_num old\n+ line_num new') into this file,
run it, and it updates files and commits changes automatically.
"""

import os
import sys
import re

def apply_changes(snippet):
    lines = snippet.strip().split('\n')
    current_file = None
    changes = {}
    
    # Parse snippet
    for line in lines:
        line = line.strip()
        if line.startswith('FILE:'):
            current_file = line.split('FILE:')[1].strip()
            changes[current_file] = []
        elif line.startswith('-') or line.startswith('+'):
            if current_file:
                changes[current_file].append(line)
    
    # Apply changes
    for file_path, diffs in changes.items():
        if not os.path.exists(file_path):
            print(f"Error: File {file_path} not found")
            continue
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        for diff in diffs:
            match = re.match(r'([-+])\s*(\d+)\s*(.*)', diff)
            if not match:
                print(f"Invalid diff line: {diff}")
                continue
            action, line_num, content = match.groups()
            line_num = int(line_num) - 1  # Convert to 0-based index
            if action == '-':
                if 0 <= line_num < len(lines) and lines[line_num].strip() == content.strip():
                    lines[line_num] = ''
                else:
                    print(f"Warning: Line {line_num + 1} in {file_path} doesn't match '{content}'")
            elif action == '+':
                if 0 <= line_num <= len(lines):
                    lines.insert(line_num, content + '\n')
                else:
                    print(f"Warning: Line {line_num + 1} out of range in {file_path}")
        with open(file_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
        os.system(f"git add {file_path}")
    
    os.system('git commit -m "Applied yeast changes"')

if __name__ == "__main__":
    # Paste your diff snippet here between the triple quotes
    snippet = """
    """
    if not snippet.strip():
        print("Please paste a diff snippet into yeast.py between the triple quotes and run again.")
        sys.exit(1)
    apply_changes(snippet)
    print("Changes applied and committed.")