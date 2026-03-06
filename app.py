# app.py
from flask import Flask, request, render_template, jsonify, Response, redirect, url_for
from wheat.field_manager import FieldManager
from wheat.paths import load_config, load_projects, save_projects, load_project_config
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
DB_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "wheat.db")


# ---------------------------------------------------------------------------
# Thread-safe state registry — one entry per active project
# ---------------------------------------------------------------------------

class FieldState:
    """Thread-safe registry of per-project field managers."""

    def __init__(self):
        self._lock = threading.Lock()
        self._projects = {}  # project_id -> {"manager", "sowing", "tending_thread"}

    def _ensure_project(self, project_id):
        """Get or create state for a project. Must be called under _lock."""
        if project_id not in self._projects:
            config = load_project_config(project_id)
            self._projects[project_id] = {
                "manager": FieldManager(project_id=project_id, config=config),
                "sowing": False,
                "tending_thread": None,
            }
        return self._projects[project_id]

    def manager(self, project_id):
        with self._lock:
            return self._ensure_project(project_id)["manager"]

    def try_start_sowing(self, project_id):
        with self._lock:
            p = self._ensure_project(project_id)
            if p["sowing"]:
                return False
            p["sowing"] = True
            return True

    def finish_sowing(self, project_id):
        with self._lock:
            if project_id in self._projects:
                self._projects[project_id]["sowing"] = False

    def reset_manager(self, project_id):
        with self._lock:
            config = load_project_config(project_id)
            self._projects[project_id] = {
                "manager": FieldManager(project_id=project_id, config=config),
                "sowing": False,
                "tending_thread": None,
            }

    def ensure_tending(self, project_id):
        with self._lock:
            p = self._ensure_project(project_id)
            if p["tending_thread"] and p["tending_thread"].is_alive():
                return
            t = threading.Thread(target=p["manager"].tend_field, daemon=True)
            p["tending_thread"] = t
            t.start()

    def clear(self, project_id):
        with self._lock:
            if project_id in self._projects:
                self._projects[project_id]["manager"].seeds = []
                self._projects[project_id]["tending_thread"] = None

    def active_projects(self):
        """Return list of project_ids that have a running tending thread."""
        with self._lock:
            return [pid for pid, p in self._projects.items()
                    if p["tending_thread"] and p["tending_thread"].is_alive()]


state = FieldState()


# ---------------------------------------------------------------------------
# Database setup with migration
# ---------------------------------------------------------------------------

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT,
        log TEXT,
        prompt_tokens INTEGER DEFAULT 0,
        completion_tokens INTEGER DEFAULT 0,
        total_tokens INTEGER DEFAULT 0,
        project_id TEXT DEFAULT 'default'
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
        project_id TEXT DEFAULT 'default',
        FOREIGN KEY (run_id) REFERENCES runs(id)
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS api_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        seed_id INTEGER,
        request_file TEXT,
        response_file TEXT,
        FOREIGN KEY (seed_id) REFERENCES seeds(id)
    )''')

    # Migration: add project_id to existing tables if missing
    existing_cols = {row[1] for row in c.execute("PRAGMA table_info(runs)").fetchall()}
    if "project_id" not in existing_cols:
        c.execute("ALTER TABLE runs ADD COLUMN project_id TEXT DEFAULT 'default'")
    existing_cols = {row[1] for row in c.execute("PRAGMA table_info(seeds)").fetchall()}
    if "project_id" not in existing_cols:
        c.execute("ALTER TABLE seeds ADD COLUMN project_id TEXT DEFAULT 'default'")

    conn.commit()
    conn.close()


init_db()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_latest_run(project_id="default"):
    conn = sqlite3.connect(DB_PATH, timeout=15)
    c = conn.cursor()
    c.execute("SELECT id, timestamp, log FROM runs WHERE project_id = ? ORDER BY id DESC LIMIT 1", (project_id,))
    run = c.fetchone()
    if run:
        run_id, timestamp, log = run
        c.execute("SELECT seed_id, task, status, output, code_file, test_result FROM seeds WHERE run_id = ? AND project_id = ?", (run_id, project_id))
        seeds = c.fetchall()
        conn.close()
        return log, {"timestamp": timestamp, "seeds": {row[0]: {"task": row[1], "status": row[2], "output": json.loads(row[3]) if row[3] else [], "code_file": row[4], "test_result": row[5]} for row in seeds}}
    conn.close()
    return None, None


# ---------------------------------------------------------------------------
# Routes: Dashboard
# ---------------------------------------------------------------------------

@app.route("/")
def dashboard():
    projects = load_projects()
    active = state.active_projects()

    # Enrich with latest run info
    project_list = []
    for pid, pdata in projects.items():
        log, status_data = get_latest_run(pid)
        seeds = status_data["seeds"] if status_data else {}
        fruitful = sum(1 for s in seeds.values() if s["status"] == "Fruitful")
        barren = sum(1 for s in seeds.values() if s["status"] == "Barren")
        growing = sum(1 for s in seeds.values() if s["status"] in ("Growing", "Repairing"))

        # Determine provider from project config
        pconfig = load_project_config(pid)
        provider = pconfig.get("llm_api", "venice")
        models = pconfig.get("models", {})

        project_list.append({
            "id": pid,
            "name": pdata.get("name", pid),
            "description": pdata.get("description", ""),
            "active": pid in active,
            "provider": provider,
            "models": models,
            "fruitful": fruitful,
            "barren": barren,
            "growing": growing,
            "total_seeds": len(seeds),
        })

    return render_template("dashboard.html", projects=project_list)


# ---------------------------------------------------------------------------
# Routes: Project-scoped
# ---------------------------------------------------------------------------

@app.route("/projects/<project_id>")
def project_field(project_id):
    projects = load_projects()
    if project_id not in projects:
        return "Project not found", 404
    log, status_data = get_latest_run(project_id)
    log = log or "Field not yet sowed."
    status = status_data["seeds"] if status_data else {}
    config = load_project_config(project_id)
    project = projects[project_id]
    return render_template("field.html",
                           log=log, status=status,
                           config=config,
                           config_json=json.dumps(config, indent=2),
                           project_id=project_id,
                           project_name=project.get("name", project_id),
                           active=project_id in state.active_projects())


@app.route("/projects/<project_id>/sow", methods=["POST"])
def project_sow(project_id):
    if not state.try_start_sowing(project_id):
        return jsonify({"message": "Sowing already in progress."}), 400
    try:
        data = request.get_json() or {}
        guidance = data.get("guidance") or "No user input—sow tasks to improve wheat seeds."

        get_stewards_map(include_params=True, include_descriptions=True)
        stewards_map_str = get_map_as_string(include_params=True, include_descriptions=True)

        config = load_project_config(project_id)

        strategist_prompt = config["strategist_prompt"].format(
            stewards_map=stewards_map_str,
            file_contents=stewards_map_str,
            seeds_per_run=config["seeds_per_run"],
            guidance=guidance
        )
        coder_prompt_template = config["coder_prompt"].format(
            stewards_map=stewards_map_str,
            file_contents=stewards_map_str,
            task="{task}"
        )

        state.reset_manager(project_id)
        state.manager(project_id).sow_field(guidance, strategist_prompt=strategist_prompt, coder_prompt=coder_prompt_template)
        state.ensure_tending(project_id)
        return jsonify({"message": f"Seeds sowed for {project_id} with guidance: '{guidance}'"})
    except Exception as e:
        print(f"[{project_id}] Sowing failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"message": f"Sowing failed: {str(e)}"}), 500
    finally:
        state.finish_sowing(project_id)


@app.route("/projects/<project_id>/stream")
def project_stream(project_id):
    def event_stream():
        while True:
            log, status_data = get_latest_run(project_id)
            log = log or "Field not yet sowed."
            status = status_data["seeds"] if status_data else {}
            html = render_template("partials/field_status.html", log=log, status=status)
            escaped = html.replace("\n", "\ndata: ")
            yield f"data: {escaped}\n\n"
            time.sleep(1)
    return Response(event_stream(), mimetype="text/event-stream")


@app.route("/projects/<project_id>/pause")
def project_pause(project_id):
    wheat_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "wheat")
    open(os.path.join(wheat_dir, f"pause_{project_id}.txt"), "w").close()
    return "Paused."


@app.route("/projects/<project_id>/resume")
def project_resume(project_id):
    wheat_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "wheat")
    pause_file = os.path.join(wheat_dir, f"pause_{project_id}.txt")
    if os.path.exists(pause_file):
        os.remove(pause_file)
    state.ensure_tending(project_id)
    return "Resumed."


@app.route("/projects/<project_id>/clear")
def project_clear(project_id):
    wheat_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "wheat")
    pause_file = os.path.join(wheat_dir, f"pause_{project_id}.txt")
    if os.path.exists(pause_file):
        os.remove(pause_file)
    state.clear(project_id)
    return "Cleared experiments."


@app.route("/projects/<project_id>/success")
def project_success(project_id):
    log, status_data = get_latest_run(project_id)
    summary = "No successful seeds found."
    if status_data:
        successful = [f"Seed {sid}: {info['task']} - {info['output'][-1] if info['output'] else 'No output'}"
                      for sid, info in status_data["seeds"].items() if info["status"] == "Fruitful"]
        summary = "\n".join(successful) if successful else summary
    return jsonify({"successful_seeds": summary})


@app.route("/projects/<project_id>/integrate", methods=["POST"])
def project_integrate(project_id):
    from wheat.paths import project_dir
    pdir = project_dir(project_id)
    success_dir = os.path.join(pdir, "successful_seeds")
    helpers_dir = os.path.join(pdir, "helpers")
    log, status_data = get_latest_run(project_id)
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
                shutil.copy(info["code_file"], os.path.join(success_dir, filename))
                shutil.copy(info["code_file"], os.path.join(helpers_dir, filename))
                integrated.append(filename)
                with open(info["code_file"], "r", encoding="utf-8") as f:
                    content = f.read()
                    func_match = re.search(r'def (\w+)\((.*?)\):', content)
                    func_name = func_match.group(1) if func_match else "unknown"
                    params = func_match.group(2).strip() if func_match else ""
                    purpose_match = re.search(r'"""(.*?)"""', content, re.DOTALL)
                    purpose = purpose_match.group(1).strip() if purpose_match else "Unknown"
                integrated_info[filename] = {"function": func_name, "purpose": purpose, "parameters": params}
        with open(registry_file, "w", encoding="utf-8") as f:
            json.dump(integrated_info, f, indent=2)

    return jsonify({"integrated": integrated, "message": f"Integrated {len(integrated)} seeds."})


@app.route("/projects/<project_id>/config", methods=["POST"])
def project_update_config(project_id):
    try:
        new_settings = request.get_json()
        projects = load_projects()
        if project_id not in projects:
            return jsonify({"message": "Project not found"}), 404
        # Merge new settings into project
        projects[project_id].update(new_settings)
        save_projects(projects)
        state.reset_manager(project_id)
        return jsonify({"message": f"Config updated for {project_id}."})
    except Exception as e:
        return jsonify({"message": f"Failed: {str(e)}"}), 400


# ---------------------------------------------------------------------------
# Routes: Project management
# ---------------------------------------------------------------------------

@app.route("/projects/new", methods=["GET", "POST"])
def new_project():
    if request.method == "GET":
        return render_template("new_project.html")

    data = request.get_json() or request.form.to_dict()
    project_id = data.get("project_id", "").strip().lower().replace(" ", "_")
    if not project_id or project_id == "new":
        return jsonify({"message": "Invalid project ID"}), 400

    projects = load_projects()
    if project_id in projects:
        return jsonify({"message": f"Project '{project_id}' already exists"}), 400

    project = {
        "name": data.get("name", project_id),
        "description": data.get("description", ""),
        "active": True,
        "llm_api": data.get("llm_api", "venice"),
        "models": {
            "strategist": data.get("model_strategist", ""),
            "coder": data.get("model_coder", ""),
            "rescuer": data.get("model_rescuer", ""),
        },
        "seeds_per_run": int(data.get("seeds_per_run", 3)),
    }
    # Only include non-empty model entries (fall back to base config)
    project["models"] = {k: v for k, v in project["models"].items() if v}
    if data.get("strategist_prompt"):
        project["strategist_prompt"] = data["strategist_prompt"]
    if data.get("coder_prompt"):
        project["coder_prompt"] = data["coder_prompt"]

    projects[project_id] = project
    save_projects(projects)
    return jsonify({"message": f"Project '{project_id}' created", "redirect": f"/projects/{project_id}"})


@app.route("/models")
def get_models():
    from wheat.sower import Sower
    sower = Sower()
    models = sower.get_available_models()
    return jsonify({"models": models})


if __name__ == "__main__":
    app.run(port=5001, threaded=True)
