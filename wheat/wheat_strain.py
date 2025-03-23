#wheat/wheat_strain.py
import subprocess
import os
import time
import json
import requests
import sqlite3
from datetime import datetime
import random
import re
import threading

db_lock = threading.Lock()

class WheatStrain:
    def __init__(self, task, strain_id, coder_model):
        self.task = task
        self.strain_id = strain_id
        self.coder_model = coder_model
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "config.json"), "r") as f:
            self.config = json.load(f)
        self.llm_api = self.config.get("llm_api", "venice")
        self.lifespan = self.config["lifespan"]
        self.strain_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "strains", f"wheat_{strain_id}")
        self.start_time = time.time()
        os.makedirs(self.strain_dir, exist_ok=True)
        self.progress = {
            "task": task,
            "status": "Growing",
            "output": [],
            "retry_count": 0,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "code_file": "",
            "test_result": ""
        }
        self.code = ""
        self.api_key = os.environ.get("VENICE_API_KEY") or "MISSING_KEY"
        self.retry_count = 0
        if "API error" not in task and not self.code:
            print(f"Strain {self.strain_id}: Initializing with task '{task}'")
            try:
                self.generate_code()
            except Exception as e:
                print(f"Strain {self.strain_id}: Initialization failed - {str(e)}")
                self.progress["status"] = "Barren"
                self.progress["output"].append(f"Init failed: {str(e)[:100]}")
            self.save_progress()

    def generate_code(self, rescue_code=None, rescue_error=None):
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        if rescue_code and rescue_error:
            self.progress["status"] = "Repairing"
            prompt = f"{self.config['coder_prompt'].format(task=self.task)}\nPrevious attempt failed with error:\n{rescue_error}\nPrevious code:\n{rescue_code}"
        else:
            self.progress["status"] = "Growing"
            prompt = self.config["coder_prompt"].format(task=self.task)
        payload = {
            "model": self.coder_model,
            "messages": [{"role": "system", "content": prompt}],
            "max_tokens": self.config["max_tokens"]
        }
        retries = 5
        sunshine_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "logs", "sunshine")
        os.makedirs(sunshine_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        print(f"Strain {self.strain_id}: Starting code generation")
        with db_lock:
            conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "wheat.db"))
            c = conn.cursor()
            for attempt in range(retries):
                try:
                    time.sleep(2)
                    with open(os.path.join(sunshine_dir, f"{timestamp}_{self.llm_api}_request.json"), "w", encoding="utf-8") as f:
                        json.dump(payload, f, indent=2)
                    print(f"Strain {self.strain_id}: Sending coder API request (attempt {attempt + 1}/{retries})")
                    response = requests.post(self.config["venice_api_url"], headers=headers, json=payload, timeout=10)
                    response.raise_for_status()
                    raw_response = response.json()
                    with open(os.path.join(sunshine_dir, f"{timestamp}_{self.llm_api}_{response.status_code}.json"), "w", encoding="utf-8") as f:
                        json.dump(raw_response, f, indent=2)
                    c.execute("INSERT INTO api_logs (strain_id, timestamp, request, response) VALUES (?, ?, ?, ?)",
                              (self.strain_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), json.dumps(payload), json.dumps(raw_response)))
                    raw_code = raw_response["choices"][0]["message"]["content"].strip()
                    tokens_used = response.headers.get("x-total-tokens", "Unknown")
                    self.progress["output"].append(f"Sent prompt (snippet): {prompt[:100]}...")
                    self.progress["output"].append(f"Received response (snippet): {raw_code[:100]}...")
                    self.progress["output"].append(f"Tokens used: {tokens_used}")
                    print(f"Strain {self.strain_id}: Coder API response received")
                    start = raw_code.find("```python") + 9
                    end = raw_code.rfind("```")
                    if start > 8 and end > start:
                        code = raw_code[start:end].strip()
                    else:
                        code = raw_code
                    code = "\n".join(line for line in code.split("\n") if not line.strip().startswith("#") and not line.strip().startswith("```"))
                    code = re.sub(r"logging\.basicConfig$$ (.*?) $$", r"logging.basicConfig(\1, filename='logs/api_usage.log')", code)
                    self.code = code
                    log_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "strains", "generated")
                    os.makedirs(log_dir, exist_ok=True)
                    self.progress["code_file"] = os.path.join(log_dir, f"wheat_{self.strain_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py")
                    with open(self.progress["code_file"], "w", encoding="utf-8") as f:
                        f.write(code)
                    print(f"Strain {self.strain_id}: Code file written to {self.progress['code_file']}")
                    break
                except requests.Timeout:
                    print(f"Strain {self.strain_id}: Coder API timeout (attempt {attempt + 1}/{retries})")
                    if attempt == retries - 1:
                        self.progress["status"] = "Barren"
                        self.progress["output"].append("Code gen failed: API timeout after retries")
                    else:
                        wait_time = 2 ** attempt + random.uniform(0, 1)
                        self.progress["output"].append(f"Retrying in {wait_time:.2f}s due to timeout")
                        time.sleep(wait_time)
                except requests.RequestException as e:
                    print(f"Strain {self.strain_id}: Coder API error - {str(e)} (attempt {attempt + 1}/{retries})")
                    with open(os.path.join(sunshine_dir, f"{timestamp}_{self.llm_api}_error_{attempt}.json"), "w", encoding="utf-8") as f:
                        json.dump({"error": str(e)}, f, indent=2)
                    c.execute("INSERT INTO api_logs (strain_id, timestamp, request, response) VALUES (?, ?, ?, ?)",
                              (self.strain_id, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), json.dumps(payload), json.dumps({"error": str(e)})))
                    if attempt == retries - 1:
                        self.progress["status"] = "Barren"
                        self.progress["output"].append(f"Code gen failed: {str(e)[:100]}")
                    else:
                        wait_time = 2 ** attempt + random.uniform(0, 1)
                        self.progress["output"].append(f"Retrying in {wait_time:.2f}s due to: {str(e)[:100]}")
                        time.sleep(wait_time)
                except Exception as e:
                    print(f"Strain {self.strain_id}: Unexpected error in generate_code - {str(e)}")
                    self.progress["status"] = "Barren"
                    self.progress["output"].append(f"Unexpected error: {str(e)[:100]}")
                    break
                finally:
                    conn.commit()
                    self.save_progress()
            conn.close()

    def grow_and_reap(self):
        if "API error" in self.task:
            self.progress["status"] = "Barren"
            return f"[wheat_{self.strain_id}] {self.task}"
        elif self.code:
            script_path = os.path.join(self.strain_dir, "script.py")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(self.code)
            cmd = ["python", "-m", "unittest", script_path]
            test_result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
            run_result = subprocess.run(["python", script_path], capture_output=True, text=True, shell=True)
            output = run_result.stdout or run_result.stderr
            self.progress["test_result"] = test_result.stdout or test_result.stderr
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.progress["timestamp"] = timestamp
            if "OK" in self.progress["test_result"]:
                self.progress["status"] = "Fruitful"
                log_entry = f"[{timestamp}] [wheat_{self.strain_id}] [{self.task}] [Fruitful] [OK] [Output: {output[:50]}...] [Code: {self.progress['code_file']}]"
            else:
                error_msg = self.progress["test_result"] if self.progress["test_result"] else "Unknown error"
                if self.retry_count < 2:
                    self.retry_count += 1
                    self.progress["status"] = "Repairing"
                    self.progress["output"].append(f"Retry {self.retry_count}/2 for failure: {error_msg[-100:]}")
                    self.generate_code(self.code, error_msg)
                    return self.grow_and_reap()
                else:
                    self.progress["status"] = "Barren"
                    log_entry = f"[{timestamp}] [wheat_{self.strain_id}] [{self.task}] [Barren] [FAILED] [{error_msg[-100:]}]"
            self.progress["output"].append(log_entry)
            self.save_progress()
            return log_entry
        else:
            self.progress["status"] = "Barren"
            self.progress["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            return f"[{self.progress['timestamp']}] [wheat_{self.strain_id}] [{self.task}] [Barren] [No code generated]"

    def is_alive(self):
        return time.time() - self.start_time < self.lifespan

    def fruitfulness(self):
        fruitful = "API error" not in self.task and os.path.exists(os.path.join(self.strain_dir, "script.py")) and "OK" in self.progress.get("test_result", "")
        return fruitful

    def save_progress(self):
        with db_lock:
            conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "wheat.db"))
            c = conn.cursor()
            c.execute("UPDATE strains SET status = ?, output = ?, code_file = ?, test_result = ? WHERE strain_id = ?",
                      (self.progress["status"], json.dumps(self.progress["output"]), self.progress["code_file"], self.progress["test_result"], self.strain_id))
            conn.commit()
            conn.close()
        os.makedirs(self.strain_dir, exist_ok=True)
        with open(os.path.join(self.strain_dir, "progress.json"), "w", encoding="utf-8") as f:
            json.dump(self.progress, f)

if __name__ == "__main__":
    strain = WheatStrain("Test task", "test123", "mistral-31-24b")
    print(strain.grow_and_reap())