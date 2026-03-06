# wheat/wheat_seed.py
import subprocess
import os
import time
import json
import sqlite3
from datetime import datetime
import re
import threading
from wheat.token_steward import TokenSteward
from wheat.providers import get_provider


class WheatSeed:
    def __init__(self, task, seed_id, coder_model, config=None, project_id="default"):
        self.task = task
        self.seed_id = seed_id
        self.coder_model = coder_model
        self.project_id = project_id
        self.token_steward = TokenSteward()

        if config is None:
            with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "config.json"), "r") as f:
                config = json.load(f)
        self.config = config

        # Model tiering
        models = config.get("models", {})
        self.coder_model = models.get("coder", coder_model)
        self.rescuer_model = models.get("rescuer", self.coder_model)

        self.provider = get_provider(config)
        self.llm_api = config.get("llm_api", "venice")
        self.lifespan = config["lifespan"]

        # Project-aware paths
        base_dir = os.path.dirname(os.path.realpath(__file__))
        if project_id and project_id != "default":
            self.seed_dir = os.path.join(base_dir, "projects", project_id, "seeds", f"seed_{self.seed_id}")
        else:
            self.seed_dir = os.path.join(base_dir, "seeds", f"seed_{self.seed_id}")
        self.sunshine_dir = os.path.join(base_dir, "..", "logs", "sunshine")

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
        self.retry_count = 0
        self.coder_prompt = None  # Will be set by FieldManager

    def generate_code(self, rescue_code=None, rescue_error=None, coder_prompt=None):
        if coder_prompt:
            prompt = coder_prompt
        elif rescue_code and rescue_error:
            prompt = (f"{self.config['coder_prompt'].format(task=self.task, stewards_map='', file_contents='')}\n"
                      f"Previous attempt failed with error:\n{rescue_error}\nPrevious code:\n{rescue_code}")
        else:
            prompt = self.config["coder_prompt"].format(task=self.task, stewards_map='', file_contents='')

        # Use rescuer model for retries, coder model for first attempt
        model = self.rescuer_model if (rescue_code and rescue_error) else self.coder_model

        print(f"Seed {self.seed_id}: Starting code generation with {model}")
        try:
            text, usage = self.provider.generate(
                prompt=prompt,
                model=model,
                max_tokens=self.config["max_tokens"],
                sunshine_dir=self.sunshine_dir,
            )

            # Log to DB
            db_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "wheat.db")
            with sqlite3.connect(db_path, timeout=15) as conn:
                c = conn.cursor()
                c.execute("UPDATE runs SET prompt_tokens = prompt_tokens + ?, completion_tokens = completion_tokens + ?, total_tokens = total_tokens + ? WHERE id = (SELECT MAX(id) FROM runs WHERE project_id = ?)",
                          (usage["prompt_tokens"], usage["completion_tokens"], usage["prompt_tokens"] + usage["completion_tokens"], self.project_id))
                conn.commit()

            self.token_steward.water_used(usage["prompt_tokens"], usage["completion_tokens"])
            self.progress["output"].append(f"Seed {self.seed_id}: Prompt={usage['prompt_tokens']}, Completion={usage['completion_tokens']}, Model={model}")
            print(f"Seed {self.seed_id}: Response received from {model}")

            # Extract code from response
            raw_code = text
            start = raw_code.find("```python") + 9
            end = raw_code.rfind("```")
            code = raw_code[start:end].strip() if start > 8 and end > start else raw_code
            code = "\n".join(line for line in code.split("\n") if not line.strip().startswith("```"))
            code = re.sub(r"logging\.basicConfig\((.*?)\)", r"logging.basicConfig(\1, filename='logs/api_usage.log', level=logging.INFO)", code)
            self.code = code

            # Save generated code
            if self.project_id and self.project_id != "default":
                log_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "projects", self.project_id, "seeds", "generated")
            else:
                log_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "seeds", "generated")
            os.makedirs(log_dir, exist_ok=True)
            self.progress["code_file"] = os.path.join(log_dir, f"seed_{self.seed_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py")
            with open(self.progress["code_file"], "w", encoding="utf-8") as f:
                f.write(code)
            print(f"Seed {self.seed_id}: Code saved to {self.progress['code_file']}")
            self.save_progress()

        except Exception as e:
            print(f"Seed {self.seed_id}: Error in generate_code - {str(e)[:200]}")
            self.progress["status"] = "Barren"
            self.progress["output"].append(f"Seed {self.seed_id}: Failed - {str(e)[:100]}")
            self.save_progress()

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
        test_result = subprocess.run(cmd, capture_output=True, text=True)
        run_result = subprocess.run(["python", script_path], capture_output=True, text=True)
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
                self.progress["output"].append(f"Seed {self.seed_id}: Retry {self.retry_count}/2 with {self.rescuer_model} - {error_msg[-100:]}")
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
        conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "wheat.db"), timeout=15)
        try:
            c = conn.cursor()
            c.execute("UPDATE seeds SET status = ?, output = ?, code_file = ?, test_result = ? WHERE seed_id = ? AND project_id = ?",
                      (self.progress["status"], json.dumps(self.progress["output"]), self.progress["code_file"], self.progress["test_result"], self.seed_id, self.project_id))
            if c.rowcount == 0:
                max_id_row = c.execute("SELECT MAX(id) FROM runs WHERE project_id = ?", (self.project_id,)).fetchone()
                run_id = max_id_row[0] if max_id_row and max_id_row[0] else 1
                c.execute("INSERT INTO seeds (run_id, seed_id, task, status, output, code_file, test_result, project_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                          (run_id, self.seed_id, self.task, self.progress["status"], json.dumps(self.progress["output"]), self.progress["code_file"], self.progress["test_result"], self.project_id))
            conn.commit()
        finally:
            conn.close()
        os.makedirs(self.seed_dir, exist_ok=True)
        with open(os.path.join(self.seed_dir, "progress.json"), "w", encoding="utf-8") as f:
            json.dump(self.progress, f)
