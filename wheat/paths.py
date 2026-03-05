import os
import json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "wheat.db")
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.json")

def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)
