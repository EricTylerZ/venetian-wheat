#wheat/field_manager.py
from wheat.sower import Sower
from wheat.wheat_strain import WheatStrain, db_lock
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
            if not self.strains:
                with db_lock:
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
                        conn.commit()
                        while len(tasks) < 12:
                            tasks.extend(tasks[:12 - len(tasks)])
                        tasks = tasks[:12]
                        self.strains = []
                        for i, task in enumerate(tasks):
                            try:
                                strain = WheatStrain(task, str(i), self.sower.coder_model)
                                self.strains.append(strain)
                                c.execute("INSERT INTO strains (run_id, strain_id, task, status, output, code_file, test_result) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                          (run_id, strain.strain_id, strain.task, strain.progress["status"], json.dumps(strain.progress["output"]), strain.progress["code_file"], strain.progress["test_result"]))
                                print(f"Inserted strain {strain.strain_id} for run {run_id}")
                                conn.commit()
                            except Exception as e:
                                print(f"Error creating strain {i}: {str(e)}")
                                continue  # Skip failed strains
                        log_entry = f"Sowed {len(tasks)} strains: {', '.join(tasks)}\n"
                        c.execute("UPDATE runs SET log = log || ? WHERE id = ?", (log_entry, run_id))
                        conn.commit()
                        c.execute("SELECT * FROM runs WHERE id = ?", (run_id,))
                        print(f"Run after commit: {c.fetchone()}")
                        c.execute("SELECT * FROM strains WHERE run_id = ?", (run_id,))
                        print(f"Strains after commit: {c.fetchall()}")
                    except Exception as e:
                        print(f"Sow field error: {str(e)}")
                        conn.rollback()
                    finally:
                        conn.close()

    def tend_field(self):
        wheat_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "wheat")
        pause_file = os.path.join(wheat_dir, "pause.txt")
        with self.lock:
            while self.strains and not all(s.progress["status"] in ["Fruitful", "Barren"] for s in self.strains):
                if os.path.exists(pause_file):
                    time.sleep(5)
                    continue
                with ThreadPoolExecutor(max_workers=12) as executor:
                    results = list(executor.map(lambda s: s.grow_and_reap(), [s for s in self.strains if s.progress["status"] in ["Growing", "Repairing"]]))
                    with db_lock:
                        conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "wheat.db"))
                        c = conn.cursor()
                        for result in results:
                            c.execute("UPDATE runs SET log = log || ? WHERE id = (SELECT MAX(id) FROM runs)", (result + "\n",))
                        for strain in self.strains:
                            c.execute("UPDATE strains SET status = ?, output = ?, code_file = ?, test_result = ? WHERE strain_id = ?",
                                      (strain.progress["status"], json.dumps(strain.progress["output"]), strain.progress["code_file"], strain.progress["test_result"], strain.strain_id))
                        conn.commit()
                        conn.close()
                for strain in self.strains[:]:
                    if not strain.is_alive():
                        result = self.reaper.evaluate(strain)
                        with db_lock:
                            conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.realpath(__file__)), "..", "wheat.db"))
                            c = conn.cursor()
                            c.execute("UPDATE runs SET log = log || ? WHERE id = (SELECT MAX(id) FROM runs)", (result + "\n",))
                            new_strain = self.reaper.reseed(strain)
                            if new_strain:
                                self.strains.append(new_strain)
                                c.execute("INSERT INTO strains (run_id, strain_id, task, status, output, code_file, test_result) VALUES (?, ?, ?, ?, ?, ?, ?)",
                                          (c.execute("SELECT MAX(id) FROM runs").fetchone()[0], new_strain.strain_id, new_strain.task, new_strain.progress["status"],
                                           json.dumps(new_strain.progress["output"]), new_strain.progress["code_file"], new_strain.progress["test_result"]))
                            self.strains.remove(strain)
                            conn.commit()
                            conn.close()
                time.sleep(1)

if __name__ == "__main__":
    manager = FieldManager()
    manager.tend_field()