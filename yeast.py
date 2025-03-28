#yeast.py
"""
Yeast: Applies Git-style patch changes with context awareness.
Saves the last committed file on failure for LLM debugging.
"""

import os
import sys
import re
import shutil
import hashlib
from datetime import datetime

def get_file_hash(file_path):
    with open(file_path, "rb") as f:
        return hashlib.md5(f.read()).hexdigest()

def revert_to_last_commit(file_path):
    os.system(f"git checkout HEAD -- {file_path}")
    print(f"Moving {file_path} to baseline from recent commit.")

def apply_patch(file_path, patch_lines):
    with open(file_path, 'r', encoding='utf-8') as f:
        original_lines = f.readlines()
    
    hunks = []
    current_hunk = {'before': [], 'after': [], 'start': None}
    in_hunk = False
    
    for line in patch_lines:
        if line.startswith('@@'):
            if in_hunk:
                hunks.append(current_hunk)
                current_hunk = {'before': [], 'after': [], 'start': None}
            in_hunk = True
            match = re.match(r'@@ -(\d+),?\d* \+(\d+),?\d* @@', line)
            if match:
                current_hunk['start'] = int(match.group(1)) - 1
        elif in_hunk:
            if line.startswith('-'):
                current_hunk['before'].append(line[1:].rstrip())
            elif line.startswith('+'):
                current_hunk['after'].append(line[1:].rstrip())
            elif line.startswith(' '):
                current_hunk['before'].append(line[1:].rstrip())
                current_hunk['after'].append(line[1:].rstrip())
    if in_hunk:
        hunks.append(current_hunk)
    
    new_lines = original_lines.copy()
    offset = 0
    warnings = []
    
    for hunk in hunks:
        start = hunk['start'] + offset
        before = hunk['before']
        after = hunk['after']
        
        match_start = -1
        for i in range(max(0, start - 10), min(len(new_lines) - len(before) + 1, start + 10)):
            if all(new_lines[i + j].rstrip() == before[j] for j in range(len(before)) if before[j]):
                match_start = i
                break
        
        if match_start == -1:
            warnings.append(f"No match for hunk at {hunk['start'] + 1}: {' '.join(before[:2])}...")
            continue
        
        new_lines[match_start:match_start + len(before)] = [line + '\n' for line in after]
        offset += len(after) - len(before)
    
    return new_lines, warnings

def apply_changes(patch_file):
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    yeast_dir = f"yeast/yeast_{timestamp}"
    with open(patch_file, 'r', encoding='utf-8') as f:
        patch_lines = f.readlines()
    
    file_patch_lines = {}
    current_file = None
    for line in patch_lines:
        if line.startswith('diff --git'):
            current_file = line.split(' b/')[1].strip()
            file_patch_lines[current_file] = []
        elif current_file:
            file_patch_lines[current_file].append(line)
    
    original_hashes = {fp: get_file_hash(fp) for fp in file_patch_lines}
    for file_path in file_patch_lines:
        revert_to_last_commit(file_path)
    
    warnings = []
    committed_files = {}
    for file_path in file_patch_lines:
        # Save the reverted (committed) state
        with open(file_path, 'r', encoding='utf-8') as f:
            committed_files[file_path] = f.read()
        new_lines, hunk_warnings = apply_patch(file_path, file_patch_lines[file_path])
        warnings.extend([f"{file_path}: {w}" for w in hunk_warnings])
        if not hunk_warnings:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)
            os.system(f"git add {file_path}")
    
    if warnings:
        os.makedirs(yeast_dir, exist_ok=True)
        for file_path in file_patch_lines:
            # Save the committed version, not the failed attempt
            with open(os.path.join(yeast_dir, os.path.basename(file_path)), 'w', encoding='utf-8') as f:
                f.write(committed_files[file_path])
            os.system(f"git checkout HEAD -- {file_path}")
            print(f"Reverting {file_path} due to patch application failure.")
        with open(os.path.join(yeast_dir, "issue_log.txt"), 'w', encoding='utf-8') as f:
            f.write("Yeast auto-undo triggered due to errors:\n" + "\n".join(warnings) + "\n")
            f.write("Original hashes (before patch attempt):\n" + "\n".join(f"{fp}: {h}" for fp, h in original_hashes.items()) + "\n")
            f.write("Files saved are the last committed versions from the current branch.\n")
            f.write("Copy this log and files into an LLM to debug.\n")
        print(f"Changes failed. Reverted files to last commit. Saved committed versions to {yeast_dir}. See issue_log.txt.")
        sys.exit(1)
    
    commit_msg = f"yeast: Applied patch from {patch_file} - {len(file_patch_lines)} files updated"
    os.system(f'git commit -m "{commit_msg}"')
    print("Changes applied and committed.")

if __name__ == "__main__":
    if len(sys.argv) < 3 or sys.argv[1].lower() != "apply":
        print("Usage: python yeast.py apply <patch_file>")
        sys.exit(1)
    apply_changes(sys.argv[2])