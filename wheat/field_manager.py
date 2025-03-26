#wheat/field_manager.py
from wheat.sower import Sower
from wheat.wheat_seed import WheatSeed  # Updated import
from wheat.reaper import Reaper
from concurrent.futures import ThreadPoolExecutor
import sqlite3
import os
import json
import threading
import time
from datetime import datetime

class FieldManager:
    def __init__(self):
        self.sower = Sower()
        self.reaper = Reaper()
        self.seeds = []  # Changed from strains to seeds
        self.lock = threading.Lock()
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "config.json"), "r") as f:
            self.seeds_per_run = json.load(f).get("seeds_per_run", 3)

    def create_seed(self, seed_id, task, status, output, code_file, test_result):
        seed = WheatSeed(task, seed_id, self.sower.coder_model)
        seed.progress = {
            "task": task,
            "status": status,
            "output": json.loads(output) if output else [],
            "code_file": code_file or "",
            "test_result": test_result or ""
        }
        return seed

    def sow_field(self, guidance=None):
        with self.lock:
            conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "wheat.db"))
            c = conn.cursor()
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            try:
                c.execute("INSERT INTO runs (timestamp, log) VALUES (?, ?)", (timestamp, f"Field sowed at {time.ctime()} with coder {self.sower.coder_model}\n"))
                run_id = c.lastrowid
                print(f"Inserted run with ID {run_id} at {timestamp}")
                conn.commit()
                tasks = self.sower.sow_seeds(guidance)
                print(f"Got {len(tasks)} tasks from strategist: {tasks}")
                log_entry = f"Sowed {len(tasks)} seeds: {', '.join(tasks)}\n"
                c.execute("UPDATE runs SET log = log || ? WHERE id = ?", (log_entry, run_id))
                conn.commit()

                self.seeds = []
                for i, task in enumerate(tasks):
                    seed_id = str(i + 1)  # Start at 1
                    seed = WheatSeed(task, seed_id, self.sower.coder_model)
                    self.seeds.append(seed)
                    c.execute("INSERT INTO seeds (run_id, seed_id, task, status, output, code_file, test_result) VALUES (?, ?, ?, ?, ?, ?, ?)",
                              (run_id, seed.seed_id, seed.task, seed.progress["status"], json.dumps(seed.progress["output"]), seed.progress["code_file"], seed.progress["test_result"]))
                    print(f"Inserted seed {seed.seed_id} for run {run_id}")
                conn.commit()
                time.sleep(1)
            except Exception as e:
                print(f"Sow field error: {str(e)}")
                conn.rollback()
                raise
            finally:
                conn.close()

    def tend_field(self):
        wheat_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "wheat")
        pause_file = os.path.join(wheat_dir, "pause.txt")
        while True:
            with self.lock:
                if not self.seeds:
                    conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "wheat.db"))
                    c = conn.cursor()
                    c.execute("SELECT id FROM runs ORDER BY id DESC LIMIT 1")
                    run_row = c.fetchone()
                    run_id = run_row[0] if run_row else None
                    if run_id:
                        c.execute("SELECT seed_id, task, status, output, code_file, test_result FROM seeds WHERE run_id = ?", (run_id,))
                        seeds = c.fetchall()
                        self.seeds = [self.create_seed(row[0], row[1], row[2], row[3], row[4], row[5]) for row in seeds]
                        print(f"Loaded {len(self.seeds)} seeds from run {run_id}")
                    conn.close()
                if not self.seeds or all(s.progress["status"] in ["Fruitful", "Barren"] for s in self.seeds):
                    time.sleep(5)
                    continue
                if os.path.exists(pause_file):
                    time.sleep(5)
                    continue

                # Generate code with staggered concurrency
                growing_seeds = [s for s in self.seeds if s.progress["status"] in ["Growing", "Repairing"]]
                with ThreadPoolExecutor(max_workers=self.seeds_per_run) as executor:
                    futures = []
                    for i, seed in enumerate(growing_seeds):
                        time.sleep(i)  # Stagger start by 1s per seed
                        futures.append(executor.submit(seed.generate_code))
                    for future in futures:
                        future.result()  # Wait for all to complete
                time.sleep(1)

                # Test seeds concurrently
                results = []
                with ThreadPoolExecutor(max_workers=self.seeds_per_run) as executor:
                    futures = [executor.submit(s.grow_and_reap) for s in growing_seeds]
                    results = [future.result() for future in futures]
                conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "wheat.db"))
                c = conn.cursor()
                for result in results:
                    c.execute("UPDATE runs SET log = log || ? WHERE id = (SELECT MAX(id) FROM runs)", (result + "\n",))
                for seed in self.seeds:
                    c.execute("UPDATE seeds SET status = ?, output = ?, code_file = ?, test_result = ? WHERE seed_id = ?",
                              (seed.progress["status"], json.dumps(seed.progress["output"]), seed.progress["code_file"], seed.progress["test_result"], seed.seed_id))
                conn.commit()
                conn.close()
                print(f"Updated database with {len(results)} results")
                time.sleep(1)

                # Rescue failed seeds
                for seed in self.seeds[:]:
                    if not seed.is_alive() or seed.progress["status"] == "Barren":
                        result = self.reaper.evaluate(seed)
                        new_seed = self.reaper.reseed(seed)
                        conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "wheat.db"))
                        c = conn.cursor()
                        c.execute("UPDATE runs SET log = log || ? WHERE id = (SELECT MAX(id) FROM runs)", (result + "\n",))
                        if new_seed:
                            self.seeds.append(new_seed)
                            c.execute("INSERT INTO seeds (run_id, seed_id, task, status, output, code_file, test_result) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                      (c.execute("SELECT MAX(id) FROM runs").fetchone()[0], new_seed.seed_id, new_seed.task, new_seed.progress["status"],
                                       json.dumps(new_seed.progress["output"]), new_seed.progress["code_file"], new_seed.progress["test_result"]))
                        self.seeds.remove(seed)
                        conn.commit()
                        conn.close()
                time.sleep(1)