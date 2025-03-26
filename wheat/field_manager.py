#wheat/field_manager.py
from wheat.sower import Sower
from wheat.wheat_strain import WheatStrain
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
        self.strains = []
        self.lock = threading.Lock()
        # Load seeds_per_run from config
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "config.json"), "r") as f:
            self.seeds_per_run = json.load(f).get("seeds_per_run", 3)

    def create_strain(self, strain_id, task, status, output, code_file, test_result):
        strain = WheatStrain(task, strain_id, self.sower.coder_model)
        strain.progress = {
            "task": task,
            "status": status,
            "output": json.loads(output) if output else [],
            "code_file": code_file or "",
            "test_result": test_result or ""
        }
        return strain

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

                self.strains = []
                for i, task in enumerate(tasks):
                    strain_id = str(i + 1)  # Start numbering at 1
                    strain = WheatStrain(task, strain_id, self.sower.coder_model)
                    self.strains.append(strain)
                    c.execute("INSERT INTO strains (run_id, strain_id, task, status, output, code_file, test_result) VALUES (?, ?, ?, ?, ?, ?, ?)",
                              (run_id, strain.strain_id, strain.task, strain.progress["status"], json.dumps(strain.progress["output"]), strain.progress["code_file"], strain.progress["test_result"]))
                    print(f"Inserted seed {strain.strain_id} for run {run_id}")
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
                if not self.strains:
                    conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "wheat.db"))
                    c = conn.cursor()
                    c.execute("SELECT id FROM runs ORDER BY id DESC LIMIT 1")
                    run_row = c.fetchone()
                    run_id = run_row[0] if run_row else None
                    if run_id:
                        c.execute("SELECT strain_id, task, status, output, code_file, test_result FROM strains WHERE run_id = ?", (run_id,))
                        strains = c.fetchall()
                        self.strains = [self.create_strain(row[0], row[1], row[2], row[3], row[4], row[5]) for row in strains]
                        print(f"Loaded {len(self.strains)} seeds from run {run_id}")
                    conn.close()
                if not self.strains or all(s.progress["status"] in ["Fruitful", "Barren"] for s in self.strains):
                    time.sleep(5)
                    continue
                if os.path.exists(pause_file):
                    time.sleep(5)
                    continue

                # Generate code with spacing to avoid API overload
                for strain in [s for s in self.strains if s.progress["status"] in ["Growing", "Repairing"]]:
                    strain.generate_code()
                    time.sleep(3)  # Space out API calls by 3 seconds
                time.sleep(1)

                # Test strains sequentially with delay
                results = []
                for strain in [s for s in self.strains if s.progress["status"] in ["Growing", "Repairing"]]:
                    result = strain.grow_and_reap()
                    results.append(result)
                    time.sleep(1)  # Small delay to ensure DB writes
                    print(f"Processed seed {strain.strain_id}: {result}")

                conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "wheat.db"))
                c = conn.cursor()
                for result in results:
                    c.execute("UPDATE runs SET log = log || ? WHERE id = (SELECT MAX(id) FROM runs)", (result + "\n",))
                for strain in self.strains:
                    c.execute("UPDATE strains SET status = ?, output = ?, code_file = ?, test_result = ? WHERE strain_id = ?",
                              (strain.progress["status"], json.dumps(strain.progress["output"]), strain.progress["code_file"], strain.progress["test_result"], strain.strain_id))
                conn.commit()
                conn.close()
                time.sleep(1)

                # Rescue failed strains
                for strain in self.strains[:]:
                    if not strain.is_alive() or strain.progress["status"] == "Barren":
                        result = self.reaper.evaluate(strain)
                        new_strain = self.reaper.reseed(strain)
                        conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "wheat.db"))
                        c = conn.cursor()
                        c.execute("UPDATE runs SET log = log || ? WHERE id = (SELECT MAX(id) FROM runs)", (result + "\n",))
                        if new_strain:
                            self.strains.append(new_strain)
                            c.execute("INSERT INTO strains (run_id, strain_id, task, status, output, code_file, test_result) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                      (c.execute("SELECT MAX(id) FROM runs").fetchone()[0], new_strain.strain_id, new_strain.task, new_strain.progress["status"],
                                       json.dumps(new_strain.progress["output"]), new_strain.progress["code_file"], new_strain.progress["test_result"]))
                        self.strains.remove(strain)
                        conn.commit()
                        conn.close()
                time.sleep(1)