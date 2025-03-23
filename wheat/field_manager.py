#wheat/field_manager.py
from wheat.sower import Sower
from wheat.wheat_strain import WheatStrain
from wheat.reaper import Reaper
from concurrent.futures import ThreadPoolExecutor
import time
import os
import json
import threading
from datetime import datetime

class FieldManager:
    def __init__(self):
        self.sower = Sower()
        self.reaper = Reaper()
        self.strains = []
        self.lock = threading.Lock()
        self.log_path = None  # Set only when sowing
        self.status_path = None  # Set only when sowing
        self.log = None  # Opened only when sowing

    def sow_field(self, guidance=None):
        with self.lock:
            if not self.strains:
                wheat_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..")
                os.makedirs(os.path.join(wheat_dir, "logs", "runs"), exist_ok=True)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                self.log_path = os.path.join(wheat_dir, "logs", "runs", f"run_{timestamp}.txt")
                self.status_path = os.path.join(wheat_dir, "logs", "runs", f"field_status_{timestamp}.json")
                with open(self.log_path, "w", encoding="utf-8") as f:
                    f.write(f"Field sowed at {time.ctime()} with coder {self.sower.coder_model}\n")
                self.log = open(self.log_path, "a", encoding="utf-8")
                tasks = self.sower.sow_seeds(guidance)
                while len(tasks) < 12:
                    tasks.extend(tasks[:12 - len(tasks)])
                tasks = tasks[:12]
                with ThreadPoolExecutor(max_workers=12) as executor:
                    self.strains = list(executor.map(lambda i_t: WheatStrain(i_t[1], f"{i_t[0]}", self.sower.coder_model), enumerate(tasks)))
                self.log.write(f"Sowed {len(tasks)} strains: {', '.join(tasks)}\n")
                self.log.flush()
            self.update_status()

    def tend_field(self):
        with self.lock:
            if self.strains:
                with ThreadPoolExecutor(max_workers=12) as executor:
                    results = list(executor.map(lambda s: s.grow_and_reap(), [s for s in self.strains if s.progress["status"] in ["Growing", "Repairing"]]))
                    for result in results:
                        self.log.write(f"{result}\n")
                        self.log.flush()
                for strain in self.strains[:]:
                    if not strain.is_alive():
                        result = self.reaper.evaluate(strain)
                        self.log.write(f"{result}\n")
                        new_strain = self.reaper.reseed(strain)
                        if new_strain:
                            self.strains.append(new_strain)
                            self.log.write(f"Resowed: {new_strain.task}\n")
                        self.strains.remove(strain)
                self.update_status()

    def update_status(self):
        if self.status_path:  # Only update if a run has been sown
            status = {strain.strain_id: strain.progress for strain in self.strains}
            with open(self.status_path, "w", encoding="utf-8") as f:
                json.dump(status, f, indent=2)
            if self.log and not self.log.closed:
                self.log.flush()

if __name__ == "__main__":
    manager = FieldManager()
    manager.tend_field()