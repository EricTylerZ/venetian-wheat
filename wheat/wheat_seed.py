# wheat/wheat_seed.py
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
from wheat.token_steward import TokenSteward

class WheatSeed:
    def __init__(self, task, seed_id, coder_model):
        self.task = task
        self.seed_id = seed_id
        self.coder_model = coder_model
        self.token_steward = TokenSteward()
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "config.json"), "r") as f:
            self.config = json.load(f)
        self.llm_api = self.config.get("llm_api", "venice")
        self.lifespan = self.config["lifespan"]
        self.seed_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "seeds", f"seed_{self.seed_id}")
        self.start_time = time.time()
        os.makedirs(self.seed_dir, exist_ok=True)
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
        self.coder_prompt = None  # Will be set by FieldManager

    def generate_code(self, rescue_code=None, rescue_error=None, coder_prompt=None):
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        # Use provided coder_prompt or default
        if coder_prompt:
            prompt = coder_prompt
        else:
            prompt = (f"{self.config['coder_prompt'].format(task=self.task, stewards_map='', file_contents='')}\nPrevious attempt failed with error:\n{rescue_error}\nPrevious code:\n{rescue_code}"
                      if rescue_code and rescue_error else self.config["coder_prompt"].format(task=self.task, stewards_map='', file_contents=''))
        payload = {
            "model": self.coder_model,
            "messages": [{"role": "system", "content": prompt}],
            "max_tokens": self.config["max_tokens"]
        }
        retries = 3
        sunshine_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "logs", "sunshine")
        os.makedirs(sunshine_dir, exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
        request_file = f"{timestamp}_{self.llm_api}_request.json"
        response_file = f"{timestamp}_{self.llm_api}_200.json"
        print(f"Seed {self.seed_id}: Starting code generation")
        for attempt in range(retries):
            try:
                tokens_estimate = len(prompt) // 4 + self.config["max_tokens"]
                print(f"Seed {self.seed_id}: Sending coder API request (attempt {attempt + 1}/{retries})")
                with open(os.path.join(sunshine_dir, request_file), "w", encoding="utf-8") as f:
                    json.dump(payload, f, indent=2)
                response = requests.post(self.config["venice_api_url"], headers=headers, json=payload, timeout=self.config["timeout"])
                response.raise_for_status()
                raw_response = response.json()
                with open(os.path.join(sunshine_dir, response_file), "w", encoding="utf-8") as f:
                    json.dump(raw_response, f, indent=2)
                conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "wheat.db"), timeout=15)
                c = conn.cursor()
                c.execute("SELECT id FROM seeds WHERE seed_id = ?", (self.seed_id,))
                result = c.fetchone()
                if result:
                    db_seed_id = result[0]
                else:
                    raise ValueError(f"Seed {self.seed_id} not found in database")
                c.execute("INSERT INTO api_logs (seed_id, request_file, response_file) VALUES (?, ?, ?)",
                          (db_seed_id, request_file, response_file))
                conn.commit()
                prompt_tokens = raw_response.get("usage", {}).get("prompt_tokens", tokens_estimate)
                completion_tokens = raw_response.get("usage", {}).get("completion_tokens", 0)
                c.execute("UPDATE runs SET prompt_tokens = prompt_tokens + ?, completion_tokens = completion_tokens + ?, total_tokens = total_tokens + ? WHERE id = (SELECT MAX(id) FROM runs)",
                          (prompt_tokens, completion_tokens, prompt_tokens + completion_tokens))
                conn.commit()
                conn.close()
                self.token_steward.water_used(prompt_tokens, completion_tokens)
                self.progress["output"].append(f"Seed {self.seed_id}: Prompt={prompt_tokens}, Completion={completion_tokens}")
                print(f"Seed {self.seed_id}: Coder API response received")
                raw_code = raw_response["choices"][0]["message"]["content"].strip()
                start = raw_code.find("```python") + 9
                end = raw_code.rfind("```")
                code = raw_code[start:end].strip() if start > 8 and end > start else raw_code
                code = "\n".join(line for line in code.split("\n") if not line.strip().startswith("#") and not line.strip().startswith("```"))
                code = re.sub(r"logging\.basicConfig$$   (.*?)   $$", r"logging.basicConfig(\1, filename='logs/api_usage.log', level=logging.INFO)", code)
                self.code = code
                log_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "seeds", "generated")
                os.makedirs(log_dir, exist_ok=True)
                self.progress["code_file"] = os.path.join(log_dir, f"seed_{self.seed_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py")
                with open(self.progress["code_file"], "w", encoding="utf-8") as f:
                    f.write(code)
                print(f"Seed {self.seed_id}: Code file saved to {self.progress['code_file']} at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
                self.save_progress()
                break
            except requests.RequestException as e:
                error_file = f"{timestamp}_{self.llm_api}_error_{attempt}.json"
                print(f"Seed {self.seed_id}: Coder API error - {str(e)} (attempt {attempt + 1}/{retries})")
                with open(os.path.join(sunshine_dir, error_file), "w", encoding="utf-8") as f:
                    json.dump({"error": str(e)}, f, indent=2)
                conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "wheat.db"), timeout=15)
                c = conn.cursor()
                c.execute("SELECT id FROM seeds WHERE seed_id = ?", (self.seed_id,))
                result = c.fetchone()
                db_seed_id = result[0] if result else None
                c.execute("INSERT INTO api_logs (seed_id, request_file, response_file) VALUES (?, ?, ?)",
                          (db_seed_id, request_file, error_file))
                conn.commit()
                conn.close()
                if attempt == retries - 1:
                    self.progress["status"] = "Barren"
                    self.progress["output"].append(f"Seed {self.seed_id}: Failed - {str(e)[:100]}")
                    self.save_progress()
                else:
                    wait_time = 2 ** attempt + random.uniform(0, 1)
                    print(f"Seed {self.seed_id}: Retrying in {wait_time:.2f}s due to: {str(e)[:100]}")
                    time.sleep(wait_time)
            except Exception as e:
                print(f"Seed {self.seed_id}: Unexpected error in generate_code - {str(e)}")
                self.progress["status"] = "Barren"
                self.progress["output"].append(f"Seed {self.seed_id}: Unexpected error - {str(e)[:100]}")
                self.save_progress()
                break

    def grow_and_reap(self):
        if "API error" in self.task or not self.code:
            self.progress["status"] = "Barren"
            self.progress["timestamp"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.save_progress()
            return f"[{self.progress['timestamp']}] [seed_{self.seed_id}] [{self.task}] [Barren] [No code generated]"
        script_path = os.path.join(self.seed_dir, "script.py")
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
            log_entry = f"[{timestamp}] [seed_{self.seed_id}] [{self.task}] [Fruitful] [OK]"
        else:
            error_msg = self.progress["test_result"] if self.progress["test_result"] else "Unknown error"
            if self.retry_count < 2:
                self.retry_count += 1
                self.progress["status"] = "Repairing"
                self.progress["output"].append(f"Seed {self.seed_id}: Retry {self.retry_count}/2 - {error_msg[-100:]}")
                self.generate_code(self.code, error_msg)
                return self.grow_and_reap()
            else:
                self.progress["status"] = "Barren"
                log_entry = f"[{timestamp}] [seed_{self.seed_id}] [{self.task}] [Barren] [FAILED] [{error_msg[-100:]}]"
        self.progress["output"].append(log_entry)
        self.save_progress()
        return log_entry

    def is_alive(self):
        return time.time() - self.start_time < self.lifespan

    def fruitfulness(self):
        fruitful = "API error" not in self.task and os.path.exists(os.path.join(self.seed_dir, "script.py")) and "OK" in self.progress.get("test_result", "")
        return fruitful

    def save_progress(self):
        conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "wheat.db"))
        c = conn.cursor()
        c.execute("UPDATE seeds SET status = ?, output = ?, code_file = ?, test_result = ? WHERE seed_id = ?",
                  (self.progress["status"], json.dumps(self.progress["output"]), self.progress["code_file"], self.progress["test_result"], self.seed_id))
        if c.rowcount == 0:
            c.execute("INSERT INTO seeds (run_id, seed_id, task, status, output, code_file, test_result) VALUES (?, ?, ?, ?, ?, ?, ?)",
                      ((c.execute("SELECT MAX(id) FROM runs").fetchone()[0] if c.execute("SELECT MAX(id) FROM runs").fetchone() else 1),
                       self.seed_id, self.task, self.progress["status"], json.dumps(self.progress["output"]), self.progress["code_file"], self.progress["test_result"]))
        conn.commit()
        conn.close()
        os.makedirs(self.seed_dir, exist_ok=True)
        with open(os.path.join(self.seed_dir, "progress.json"), "w", encoding="utf-8") as f:
            json.dump(self.progress, f)