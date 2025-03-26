#wheat/reaper.py
import random
from wheat.wheat_seed import WheatSeed

class Reaper:
    def evaluate(self, seed):
        status = "fruitful" if seed.fruitfulness() else "barren"
        return f"Seed {seed.seed_id} {status}: {seed.task}"

    def reseed(self, seed):
        if seed.fruitfulness():
            new_task = seed.task + f" with {random.choice(['logging', 'optimization', 'UI'])}"
            return WheatSeed(new_task, seed.seed_id + "_1", seed.coder_model)
        return None