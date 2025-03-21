#wheat/wheat_strain.py
from concurrent.futures import ThreadPoolExecutor
import subprocess
import os
import time
import json
import requests
from datetime import datetime

class WheatStrain:
    def __init__(self, task, strain_id, coder_model):
        self.task = task
        self.strain_id = strain_id
        self.coder_model = coder_model
        with open(os.path.join(os.path.dirname(__file__), "config.json"), "r") as f:
            self.config = json.load(f)
        self.lifespan = self.config["lifespan"]
        self.strain_dir = os.path.join(os.path.dirname(__file__), "strains", f"wheat_{strain_id}")
        self.start_time = time.time()
        os.makedirs(self.strain_dir, exist_ok=True)
        self.progress = {"task": task, "status": "Growing", "output": [], "code": "", "test_result": ""}
        self.api_key = os.environ.get("VENICE_API_KEY") or "MISSING_KEY"
        if "API error" not in task:
            self.generate_code()
        self.save_progress()

    def generate_code(self, rescue_code=None, rescue_error=None):
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        if rescue_code and rescue_error:
            prompt = self.config["rescue_prompt"].format(code=rescue_code, error=rescue_error)
        else:
            prompt = self.config["coder_prompt"].format(task=self.task)
        payload = {
            "model": self.coder_model,
            "messages": [{"role": "system", "content": prompt}],
            "max_tokens": self.config["max_tokens"]
        }
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(requests.post, self.config["venice_api_url"], headers=headers, json=payload, timeout=self.config["timeout"])
            try:
                response = future.result()
                response.raise_for_status()
                raw_code = response.json()["choices"][0]["message"]["content"].strip()
                start = raw_code.find("```python") + 9
                end = raw_code.rfind("```")
                if start > 8 and end > start:
                    code = raw_code[start:end].strip()
                else:
                    code = raw_code
                code = "\n".join(line for line in code.split("\n") if not line.strip().startswith("#") and not line.strip().startswith("```"))
                self.progress["code"] = code
                log_dir = os.path.join(os.path.dirname(__file__), "logs")
                os.makedirs(log_dir, exist_ok=True)
                self.code_file = os.path.join(log_dir, f"wheat_{self.strain_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py")
                with open(self.code_file, "w", encoding="utf-8") as f:
                    f.write(code)
            except requests.RequestException as e:
                self.progress["output"].append(f"Code gen failed: {str(e)}")

    def grow_and_reap(self):
        if "API error" in self.task:
            self.progress["status"] = "Barren"
            return f"[wheat_{self.strain_id}] {self.task}"
        elif self.progress["code"]:
            script_path = os.path.join(self.strain_dir, "script.py")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(self.progress["code"])
            cmd = ["python", "-m", "unittest", script_path]
            test_result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
            run_result = subprocess.run(["python", script_path], capture_output=True, text=True, shell=True)
            output = run_result.stdout or run_result.stderr
            self.progress["test_result"] = test_result.stdout or test_result.stderr
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if "OK" in self.progress["test_result"]:
                self.progress["status"] = "Fruitful"
                log_entry = f"[{timestamp}] [wheat_{self.strain_id}] [{self.task}] [Fruitful] [OK] [Output: {output[:50]}...] [Code: {self.code_file}]"
            else:
                error_msg = self.progress['test_result'].split('\n')[0] if self.progress['test_result'] else "Unknown error"
                self.progress["status"] = "Barren"
                log_entry = f"[{timestamp}] [wheat_{self.strain_id}] [{self.task}] [Barren] [FAILED] [{error_msg}]"
                if "SyntaxError" in error_msg:
                    self.progress["output"].append(f"Attempting syntax rescue for: {error_msg}")
                    self.generate_code(self.progress["code"], error_msg)
                    return self.grow_and_reap()
            self.progress["output"].append(log_entry)
            self.save_progress()
            return log_entry
        else:
            self.progress["status"] = "Barren"
            return f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] [wheat_{self.strain_id}] [{self.task}] [Barren] [No code generated]"

    def is_alive(self):
        return time.time() - self.start_time < self.lifespan

    def fruitfulness(self):
        fruitful = "API error" not in self.task and os.path.exists(os.path.join(self.strain_dir, "script.py")) and "OK" in self.progress["test_result"]
        return fruitful

    def save_progress(self):
        with open(os.path.join(self.strain_dir, "progress.json"), "w", encoding="utf-8") as f:
            json.dump(self.progress, f)

if __name__ == "__main__":
    strain = WheatStrain("Test task", "test123", "mistral-31-24b")
    print(strain.grow_and_reap())