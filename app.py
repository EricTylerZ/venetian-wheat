# app.py
from flask import Flask, request, render_template, render_template_string, jsonify, Response
from wheat.field_manager import FieldManager
import sqlite3
import os
import json
import threading
import time
from datetime import datetime
import shutil
import re
from tools.stewards_map import get_stewards_map, get_map_as_string

app = Flask(__name__)


class FieldState:
    """Thread-safe container for all mutable application state."""

    def __init__(self):
        self._lock = threading.Lock()
        self._manager = FieldManager()
        self._sowing = False
        self._tending_thread = None

    @property
    def manager(self):
        return self._manager

    def try_start_sowing(self):
        """Atomically claim the sowing lock. Returns True if acquired."""
        with self._lock:
            if self._sowing:
                return False
            self._sowing = True
            return True

    def finish_sowing(self):
        with self._lock:
            self._sowing = False

    def reset_manager(self):
        with self._lock:
            self._manager = FieldManager()
            self._tending_thread = None

    def ensure_tending(self):
        """Start the tending thread if it isn't already running."""
        with self._lock:
            if self._tending_thread and self._tending_thread.is_alive():
                return
            self._tending_thread = threading.Thread(
                target=self._manager.tend_field, daemon=True
            )
            self._tending_thread.start()

    def stop_tending(self):
        with self._lock:
            self._tending_thread = None

    def clear(self):
        with self._lock:
            self._manager.seeds = []
            self._tending_thread = None


state = FieldState()

def init_db():
    conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.realpath(__file__)), "wheat.db"))
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        log TEXT,
        prompt_tokens INTEGER DEFAULT 0,
        completion_tokens INTEGER DEFAULT 0,
        total_tokens INTEGER DEFAULT 0
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS seeds (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id INTEGER,
        seed_id TEXT,
        task TEXT,
        status TEXT,
        output TEXT,
        code_file TEXT,
        test_result TEXT,
        FOREIGN KEY (run_id) REFERENCES runs(id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS api_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        seed_id INTEGER,
        request_file TEXT,
        response_file TEXT,
        FOREIGN KEY (seed_id) REFERENCES seeds(id)
    )''')
    conn.commit()
    conn.close()

init_db()

def get_latest_run():
    conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.realpath(__file__)), "wheat.db"))
    c = conn.cursor()
    c.execute("SELECT id, timestamp, log FROM runs ORDER BY id DESC LIMIT 1")
    run = c.fetchone()
    if run:
        run_id, timestamp, log = run
        c.execute("SELECT seed_id, task, status, output, code_file, test_result FROM seeds WHERE run_id = ?", (run_id,))
        seeds = c.fetchall()
        conn.close()
        return log, {"timestamp": timestamp, "seeds": {row[0]: {"task": row[1], "status": row[2], "output": json.loads(row[3]) if row[3] else [], "code_file": row[4], "test_result": row[5]} for row in seeds}}
    conn.close()
    return None, None

@app.route("/")
def field_status():
    log, status_data = get_latest_run()
    log = log or "Field not yet sowed."
    status = status_data["seeds"] if status_data else {}
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "config.json"), "r") as f:
        config = json.load(f)

    return render_template("field.html",
                           log=log, status=status,
                           config=config,
                           config_json=json.dumps(config, indent=2))

@app.route("/sow", methods=["POST"])
def sow():
    if not state.try_start_sowing():
        return jsonify({"message": "Sowing already in progress."}), 400
    try:
        data = request.get_json() or {}
        guidance = data.get("guidance") or "No user input—sow tasks to improve wheat seeds."

        # Save the stewards map to a file for backtracking
        get_stewards_map(include_params=True, include_descriptions=True)

        # Get the stewards map as a string for prompts
        stewards_map_str = get_map_as_string(include_params=True, include_descriptions=True)

        # Load config
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "config.json"), "r") as f:
            config = json.load(f)

        # Format strategist_prompt with the map string
        strategist_prompt = config["strategist_prompt"].format(
            stewards_map=stewards_map_str,
            file_contents=stewards_map_str,
            seeds_per_run=config["seeds_per_run"],
            guidance=guidance
        )

        # Pass coder_prompt as the raw template with tree substituted
        coder_prompt_template = config["coder_prompt"].format(
            stewards_map=stewards_map_str,
            file_contents=stewards_map_str,
            task="{task}"  # Keep as placeholder
        )

        state.reset_manager()
        state.manager.sow_field(guidance, strategist_prompt=strategist_prompt, coder_prompt=coder_prompt_template)
        state.ensure_tending()
        return jsonify({"message": f"Seeds sowed with guidance: '{guidance}'"})
    except Exception as e:
        print(f"Sowing failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"message": f"Sowing failed: {str(e)}"}), 500
    finally:
        state.finish_sowing()

@app.route("/stream")
def stream():
    def event_stream():
        while True:
            log, status_data = get_latest_run()
            log = log or "Field not yet sowed."
            status = status_data["seeds"] if status_data else {}
            # Render the partial as HTML for htmx SSE swap
            html = render_template("partials/field_status.html",
                                   log=log, status=status)
            # SSE format: each line prefixed with "data: ", blank line terminates
            escaped = html.replace("\n", "\ndata: ")
            yield f"data: {escaped}\n\n"
            time.sleep(1)
    return Response(event_stream(), mimetype="text/event-stream")

@app.route("/pause")
def pause():
    wheat_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "wheat")
    open(os.path.join(wheat_dir, "pause.txt"), "w").close()
    return "Paused."

@app.route("/resume")
def resume():
    wheat_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "wheat")
    pause_file = os.path.join(wheat_dir, "pause.txt")
    if os.path.exists(pause_file):
        os.remove(pause_file)
    state.ensure_tending()
    return "Resumed."

@app.route("/clear")
def clear():
    wheat_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "wheat")
    pause_file = os.path.join(wheat_dir, "pause.txt")
    if os.path.exists(pause_file):
        os.remove(pause_file)
    state.clear()
    return "Cleared experiments."

@app.route("/success")
def show_successful_seeds():
    log, status_data = get_latest_run()
    summary = "No successful seeds found."
    if status_data:
        successful = [f"Seed {seed_id}: {info['task']} - {info['output'][-1] if info['output'] else 'No output'}" 
                      for seed_id, info in status_data["seeds"].items() if info["status"] == "Fruitful"]
        summary = "\n".join(successful) if successful else summary
    return jsonify({"successful_seeds": summary})

@app.route("/integrate", methods=["POST"])
def integrate_successful_seeds():
    wheat_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "wheat")
    success_dir = os.path.join(wheat_dir, "successful_seeds")
    helpers_dir = os.path.join(wheat_dir, "helpers")
    log, status_data = get_latest_run()
    integrated = []
    integrated_info = {}

    registry_file = os.path.join(helpers_dir, "script_registry.json")
    if os.path.exists(registry_file):
        with open(registry_file, "r", encoding="utf-8") as f:
            integrated_info = json.load(f)

    if status_data:
        os.makedirs(success_dir, exist_ok=True)
        os.makedirs(helpers_dir, exist_ok=True)
        for seed_id, info in status_data["seeds"].items():
            if info["status"] == "Fruitful" and info["code_file"] and os.path.exists(info["code_file"]):
                filename = f"seed_{seed_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
                dest_file = os.path.join(success_dir, filename)
                shutil.copy(info["code_file"], dest_file)
                helper_file = os.path.join(helpers_dir, filename)
                shutil.copy(info["code_file"], helper_file)
                integrated.append(filename)
                with open(info["code_file"], "r", encoding="utf-8") as f:
                    content = f.read()
                    func_match = re.search(r'def (\w+)\((.*?)\):', content)
                    func_name = func_match.group(1) if func_match else "unknown_function"
                    params = func_match.group(2).strip() if func_match else "unknown"
                    purpose_match = re.search(r'"""(.*?)"""', content, re.DOTALL)
                    purpose = purpose_match.group(1).strip() if purpose_match else "Unknown purpose"
                integrated_info[filename] = {"function": func_name, "purpose": purpose, "parameters": params}
        with open(registry_file, "w", encoding="utf-8") as f:
            json.dump(integrated_info, f, indent=2)

    return jsonify({"integrated": integrated, "message": f"Integrated {len(integrated)} successful seeds into wheat/helpers/."})

@app.route("/update_config", methods=["POST"])
def update_config():
    try:
        new_config = request.get_data(as_text=True)
        parsed = json.loads(new_config)
        # Validate required keys exist
        required_keys = ["llm_api", "max_tokens", "timeout", "seeds_per_run",
                         "strategist_prompt", "coder_prompt"]
        missing = [k for k in required_keys if k not in parsed]
        if missing:
            return jsonify({"message": f"Missing required config keys: {', '.join(missing)}"}), 400
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "config.json"), "w") as f:
            f.write(new_config)
        state.reset_manager()
        return jsonify({"message": "Config updated successfully. Restart sowing or resume to apply changes."})
    except json.JSONDecodeError as e:
        return jsonify({"message": f"Invalid JSON: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"message": f"Failed to update config: {str(e)}"}), 400

@app.route("/models")
def get_models():
    from wheat.sower import Sower
    sower = Sower()
    models = sower.get_available_models()
    return jsonify({"models": models})

if __name__ == "__main__":
    app.run(port=5001, threaded=True)