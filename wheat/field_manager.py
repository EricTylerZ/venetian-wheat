#wheat/field_manager.py
from wheat.sower import Sower
from wheat.wheat_strain import WheatStrain
from wheat.reaper import Reaper
from concurrent.futures import ThreadPoolExecutor
import time
import os
import json

class FieldManager:
    def __init__(self):
        self.sower = Sower()
        self.reaper = Reaper()
        self.strains = []
        os.makedirs(os.path.join(os.path.dirname(__file__), "logs"), exist_ok=True)
        with open(os.path.join(os.path.dirname(__file__), "field_log.txt"), "w", encoding="utf-8") as f:
            f.write(f"Field sowed at {time.ctime()} with coder {self.sower.coder_model}\n")
        self.log = open(os.path.join(os.path.dirname(__file__), "field_log.txt"), "a", encoding="utf-8")
        self.update_status()

    def sow_field(self, guidance=None):
        tasks = self.sower.sow_seeds(guidance)
        while len(tasks) < 12:
            tasks.extend(tasks[:12 - len(tasks)])
        tasks = tasks[:12]
        with ThreadPoolExecutor(max_workers=12) as executor:
            self.strains = list(executor.map(lambda i_t: WheatStrain(i_t[1], f"{i_t[0]}", self.sower.coder_model), enumerate(tasks)))
        self.log.write(f"Sowed {len(tasks)} strains: {', '.join(tasks)}\n")
        self.update_status()

    def tend_field(self):
        if not self.strains:
            self.log.write("No strains—sowing new field.\n")
            self.sow_field()
        with ThreadPoolExecutor(max_workers=12) as executor:
            results = executor.map(lambda s: s.grow_and_reap(), [s for s in self.strains if s.progress["status"] == "Growing"])
            for result in results:
                self.log.write(f"{result}\n")
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
        status = {strain.strain_id: strain.progress for strain in self.strains}
        with open(os.path.join(os.path.dirname(__file__), "field_status.json"), "w", encoding="utf-8") as f:
            json.dump(status, f, indent=2)

if __name__ == "__main__":
    manager = FieldManager()
    manager.tend_field()