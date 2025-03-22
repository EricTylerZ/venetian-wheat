#tools/analyze_logs.py
import os
import subprocess
import csv
import re
from datetime import datetime

def extract_purpose(content):
    match = re.search(r'"""(.*?)"""', content, re.DOTALL)
    if match:
        return match.group(1).strip()
    match = re.search(r"'''(.*?)'''", content, re.DOTALL)
    if match:
        return match.group(1).strip()
    lines = content.split('\n')
    for line in lines:
        if line.strip().startswith('#'):
            return line.strip()[1:].strip()
    return "Unknown"

def test_script(file_path):
    try:
        cmd = ["python", "-m", "unittest", file_path]
        result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
        return "OK" in result.stdout or result.returncode == 0
    except Exception as e:
        print(f"Error testing {file_path}: {e}")
        return False

def analyze_logs():
    wheat_dir = os.path.join(os.path.dirname(__file__), "..", "wheat")
    log_dir = os.path.join(wheat_dir, "logs")
    output_file = os.path.join(wheat_dir, f"strain_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    with open(output_file, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["File", "Purpose", "Status"])
        for filename in os.listdir(log_dir):
            if filename.endswith(".py"):
                file_path = os.path.join(log_dir, filename)
                with open(file_path, "r", encoding="utf-8") as script_file:
                    content = script_file.read()
                purpose = extract_purpose(content)
                status = "Fruitful" if test_script(file_path) else "Barren"
                writer.writerow([file_path, purpose, status])
    print(f"Analysis saved to {output_file}")

if __name__ == "__main__":
    analyze_logs()