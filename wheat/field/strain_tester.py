#wheat/field/strain_tester.py
import subprocess
import time
import json
import os
import shutil

VERSIONS = [f"version_{i}" for i in range(12)]  # version_0 to version_11
TIMEOUT = 3600  # 1 hour in seconds
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # wheat/ directory

def setup_versions():
    """Create version directories and copy wheat field code into each."""
    for version in VERSIONS:
        version_dir = os.path.join(BASE_DIR, "strains", "versions", version)
        os.makedirs(version_dir, exist_ok=True)
        for file in ["sower.py", "wheat_strain.py", "field_manager.py", "harvester.py"]:
            src = os.path.join(BASE_DIR, file)
            if os.path.exists(src):
                shutil.copy(src, version_dir)

def run_version(version):
    """Launch a field manager instance in the given version directory."""
    version_dir = os.path.join(BASE_DIR, "strains", "versions", version)
    cmd = ["python", "field_manager.py"]
    process = subprocess.Popen(cmd, cwd=version_dir)
    return process

def collect_results(version):
    """Read logs and status, count fruitful strains."""
    version_dir = os.path.join(BASE_DIR, "strains", "versions", version)
    log_path = os.path.join(version_dir, "field_log.txt")
    status_path = os.path.join(version_dir, "field_status.json")
    log_content = open(log_path, "r").read() if os.path.exists(log_path) else "No log generated"
    fruitful_count = 0
    if os.path.exists(status_path):
        with open(status_path, "r") as f:
            status = json.load(f)
            fruitful_count = sum(1 for s in status.values() if s["status"] == "Fruitful")
    return {"version": version, "log": log_content, "fruitful_strains": fruitful_count}

if __name__ == "__main__":
    setup_versions()
    processes = [run_version(v) for v in VERSIONS]
    print(f"Started {len(VERSIONS)} experiments at {time.ctime()}")

    start_time = time.time()
    while time.time() - start_time < TIMEOUT:
        if all(p.poll() is not None for p in processes):
            print("All experiments finished early!")
            break
        time.sleep(10)

    results = [collect_results(v) for v in VERSIONS]
    for r in results:
        print(f"\n{r['version']}: {r['fruitful_strains']} fruitful strains")
        print(f"Log excerpt:\n{r['log'][:500]}...\n")