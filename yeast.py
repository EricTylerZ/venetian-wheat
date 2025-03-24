"""
Yeast: Applies diff-like changes to files in the Venetian Wheat project.
Automates hashing, reverts to last commit per file, and ensures full rollback on failure.
"""

import os
import sys
import re
import shutil
import hashlib
from datetime import datetime

def get_file_hash(file_path):
    """Compute MD5 hash of a file."""
    with open(file_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

def revert_to_last_commit(file_path):
    """Revert a single file to its last committed state."""
    os.system(f"git checkout HEAD -- {file_path}")
    print(f"Reverted {file_path} to last commit.")

def find_line(file_path, expected_content):
    """Find the line number of the expected content, return -1 if not found."""
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    expected = expected_content.strip()
    for i, line in enumerate(lines, 1):
        if line.strip() == expected:
            return i
    return -1

def check_mismatches(file_path, diffs):
    """Check for mismatches and report actual locations."""
    if not os.path.exists(file_path):
        return [(None, f"Error: File {file_path} not found")]
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    mismatches = []
    for diff in diffs:
        match = re.match(r'([-+])\s*(\d+)\s*(.*)', diff)
        if not match:
            mismatches.append((None, f"Invalid diff line: {diff}"))
            continue
        action, line_num, content = match.groups()
        line_num = int(line_num) - 1  # 0-based
        if action == '-':
            if 0 <= line_num < len(lines):
                actual = lines[line_num].strip()
                expected = content.strip()
                if actual != expected:
                    actual_line = find_line(file_path, expected)
                    mismatches.append((line_num + 1, f"Line {line_num + 1} expected '{expected}', found '{actual}'" + 
                                      (f", expected found at line {actual_line}" if actual_line != -1 else "")))
            else:
                mismatches.append((line_num + 1, f"Line {line_num + 1} out of range (file has {len(lines)} lines)"))
    return mismatches

def apply_changes(snippet):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    yeast_dir = f"yeast/yeast_{timestamp}"
    lines = snippet.strip().split('\n')
    current_file = None
    changes = {}
    warnings = []
    original_hashes = {}
    
    # Parse snippet and collect files
    for line in lines:
        line = line.strip()
        if line.startswith('FILE:'):
            current_file = line.split('FILE:')[1].strip()
            changes[current_file] = []
            original_hashes[current_file] = get_file_hash(current_file)
            revert_to_last_commit(current_file)  # Start from last commit
        elif line.startswith('-') or line.startswith('+'):
            if current_file:
                changes[current_file].append(line)
    
    # Check mismatches
    for file_path, diffs in changes.items():
        mismatches = check_mismatches(file_path, diffs)
        warnings.extend([f"Warning: {msg} in {file_path}" for _, msg in mismatches])
    
    # Apply changes if no critical mismatches
    if not warnings or all("out of range" not in w.lower() for w in warnings):
        for file_path, diffs in changes.items():
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            for diff in diffs:
                match = re.match(r'([-+])\s*(\d+)\s*(.*)', diff)
                if not match:
                    continue
                action, line_num, content = match.groups()
                line_num = int(line_num) - 1
                if action == '-':
                    if 0 <= line_num < len(lines):
                        lines[line_num] = ''
                    else:
                        warnings.append(f"Warning: Line {line_num + 1} out of range in {file_path}")
                elif action == '+':
                    if 0 <= line_num <= len(lines):
                        lines.insert(line_num, content + '\n')
                    else:
                        warnings.append(f"Warning: Line {line_num + 1} out of range in {file_path}")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            os.system(f"git add {file_path}")
    
    if warnings:
        os.makedirs(yeast_dir, exist_ok=True)
        for file_path in changes.keys():
            shutil.copy(file_path, os.path.join(yeast_dir, os.path.basename(file_path)))
            revert_to_last_commit(file_path)  # Revert to last commit on failure
        with open(os.path.join(yeast_dir, "issue_log.txt"), 'w', encoding='utf-8') as f:
            f.write("Yeast auto-undo triggered due to errors:\n" + "\n".join(warnings) + "\n")
            f.write("Original hashes:\n" + "\n".join(f"{fp}: {h}" for fp, h in original_hashes.items()) + "\n")
            f.write("Copy these files and this log into an LLM to generate a new diff.txt.\n")
        print(f"Changes failed. Reverted files to last commit. Saved to {yeast_dir}. See issue_log.txt.")
        sys.exit(1)
    
    commit_msg = f"yeast: Applied diff changes from diff.txt - {len(changes)} files updated"
    os.system(f'git commit -m "{commit_msg}"')
    print("Changes applied and committed.")

def undo_changes(exclude=None):
    os.system('git reset --soft HEAD^')
    os.system('git restore --staged .')
    if exclude:
        os.system(f'git checkout HEAD -- {exclude}')
    else:
        os.system('git restore .')
    print(f"Last yeast changes undone{' (kept ' + exclude + ')' if exclude else ''}.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python yeast.py [apply|undo]")
        sys.exit(1)
    
    command = sys.argv[1].lower()
    if command == "apply":
        diff_file = "diff.txt"
        if not os.path.exists(diff_file) or os.stat(diff_file).st_size == 0:
            print(f"Please paste a diff snippet into {diff_file} and run again.")
            with open(diff_file, 'w', encoding='utf-8') as f:
                f.write("# Paste diff here, e.g:\n# FILE: app.py\n# - 10 old line\n# + 10 new line\n")
            sys.exit(1)
        with open(diff_file, 'r', encoding='utf-8') as f:
            snippet = f.read()
        apply_changes(snippet)
    elif command == "undo":
        undo_changes(exclude='yeast.py')
    else:
        print(f"Unknown command: {command}. Use 'apply' or 'undo'.")
        sys.exit(1)