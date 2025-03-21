#wheat/reaper.py
import random
from wheat.wheat_strain import WheatStrain

class Reaper:
    def evaluate(self, strain):
        status = "fruitful" if strain.fruitfulness() else "barren"
        return f"Strain {strain.strain_id} {status}: {strain.task}"

    def reseed(self, strain):
        if strain.fruitfulness():
            new_task = strain.task + f" with {random.choice(['logging', 'optimization', 'UI'])}"
            return WheatStrain(new_task, strain.strain_id + "_1", strain.coder_model)
        return None