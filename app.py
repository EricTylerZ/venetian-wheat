# app.py
from flask import Flask, request, render_template_string, jsonify, Response
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
manager = FieldManager()
sowing_in_progress = False
tending_thread = None

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
    wheat_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "wheat")
    log = log or "Field not yet sowed."
    paused = os.path.exists(os.path.join(wheat_dir, "pause.txt"))
    status = status_data["seeds"] if status_data else {}
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "config.json"), "r") as f:
        config = json.load(f)

    return render_template_string("""
        <h2>Venetian Wheat Field</h2>
        <form id="sowForm" onsubmit="sowSeeds(event)">
            <textarea name="guidance" rows="4" cols="50" placeholder="Sow guidance (e.g., 'Improve seed logging')—leave blank for Venice AI to propose"></textarea><br>
            <input type="submit" value="Sow Seeds">
        </form>
        <button onclick="fetch('/pause')">Pause</button>
        <button onclick="fetch('/resume')">Resume</button>
        <button onclick="fetch('/clear')">Clear Experiments</button>
        <button onclick="showSuccess()">Show Successful Seeds</button>
        <button onclick="integrateSeeds()">Integrate Successful Seeds</button>
        <h3>Config Status</h3>
        <pre id="configDisplay">{{ config }}</pre>
        <form id="configForm" onsubmit="updateConfig(event)">
            <textarea name="config" rows="10" cols="50">{{ config }}</textarea><br>
            <input type="submit" value="Update Config">
        </form>
        <h3>Field Log (Current Run)</h3>
        <pre id="log">{{ log }}</pre>
        <h3>Field Status</h3>
        <div id="processingStatus"></div>
        <table border="1" id="statusTable">
            <tr><th>Seed</th><th>Task</th><th>Status</th><th>Output</th></tr>
            {% for seed_id, info in status.items() %}
                <tr>
                    <td>{{ seed_id }}</td>
                    <td>{{ info.task }}</td>
                    <td>{{ info.status }}</td>
                    <td>{{ info.output|join('<br>') }}</td>
                </tr>
            {% endfor %}
        </table>
        <script>
            function sowSeeds(event) {
                event.preventDefault();
                const form = document.getElementById('sowForm');
                const guidance = form.querySelector('textarea').value.trim();
                fetch('/sow', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({guidance: guidance || null})
                }).then(response => response.json())
                  .then(result => alert(result.message));
            }
            function showSuccess() {
                fetch('/success')
                    .then(response => response.json())
                    .then(data => alert(data.successful_seeds));
            }
            function integrateSeeds() {
                fetch('/integrate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'}
                }).then(response => response.json())
                  .then(data => alert(data.message));
            }
            function updateConfig(event) {
                event.preventDefault();
                const form = document.getElementById('configForm');
                const config = form.querySelector('textarea').value;
                fetch('/update_config', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: config
                }).then(response => response.json())
                  .then(result => alert(result.message));
            }
            const eventSource = new EventSource('/stream');
            eventSource.onmessage = function(event) {
                const data = JSON.parse(event.data);
                document.getElementById('log').innerText = data.log;
                document.getElementById('configDisplay').innerText = data.config;
                const table = document.getElementById('statusTable');
                table.innerHTML = '<tr><th>Seed</th><th>Task</th><th>Status</th><th>Output</th></tr>';
                Object.entries(data.status).forEach(([seed_id, info]) => {
                    const row = table.insertRow();
                    row.insertCell().innerText = seed_id;
                    row.insertCell().innerText = info.task;
                    row.insertCell().innerText = info.status;
                    row.insertCell().innerHTML = info.output.join('<br>');
                });
                document.getElementById('processingStatus').innerText = data.complete ? 'Processing complete' : 'Processing seeds...';
            };
            eventSource.onerror = function() {
                console.log('SSE error - reconnecting...');
            };
        </script>
    """, log=log, status=status, paused=paused, config=json.dumps(config, indent=2))

@app.route("/sow", methods=["POST"])
def sow():
    global sowing_in_progress, tending_thread, manager
    if sowing_in_progress:
        return jsonify({"message": "Sowing already in progress."}), 400
    sowing_in_progress = True
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
            file_contents=stewards_map_str,  # Use tree instead of file contents
            seeds_per_run=config["seeds_per_run"],
            guidance=guidance
        )
        
        # Pass coder_prompt as the raw template with tree substituted
        coder_prompt_template = config["coder_prompt"].format(
            stewards_map=stewards_map_str,
            file_contents=stewards_map_str,  # Use tree instead of file contents
            task="{task}"  # Keep as placeholder
        )
        
        # Debug prints to verify types and content
        print(f"Type of stewards_map_str: {type(stewards_map_str)}")
        print(f"Type of strategist_prompt: {type(strategist_prompt)}")
        print(f"Type of coder_prompt_template: {type(coder_prompt_template)}")
        print(f"coder_prompt_template content: {coder_prompt_template[:200]}...")  # Truncated for brevity
        
        manager = FieldManager()
        manager.sow_field(guidance, strategist_prompt=strategist_prompt, coder_prompt=coder_prompt_template)
        if not tending_thread or not tending_thread.is_alive():
            tending_thread = threading.Thread(target=manager.tend_field, daemon=True)
            tending_thread.start()
        return jsonify({"message": f"Seeds sowed with guidance: '{guidance}'"})
    except Exception as e:
        print(f"Sowing failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"message": f"Sowing failed: {str(e)}"}), 500
    finally:
        sowing_in_progress = False

@app.route("/stream")
def stream():
    def event_stream():
        while True:
            log, status_data = get_latest_run()
            log = log or "Field not yet sowed."
            status = status_data["seeds"] if status_data else {}
            complete = all(info["status"] in ["Fruitful", "Barren"] for info in status.values())
            with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "config.json"), "r") as f:
                config = json.load(f)
            yield f"data: {json.dumps({'log': log, 'status': status, 'complete': complete, 'config': json.dumps(config, indent=2)})}\n\n"
            time.sleep(1)
    return Response(event_stream(), mimetype="text/event-stream")

@app.route("/pause")
def pause():
    wheat_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "wheat")
    open(os.path.join(wheat_dir, "pause.txt"), "w").close()
    return "Paused."

@app.route("/resume")
def resume():
    global tending_thread
    wheat_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "wheat")
    pause_file = os.path.join(wheat_dir, "pause.txt")
    if os.path.exists(pause_file):
        os.remove(pause_file)
    if not tending_thread or not tending_thread.is_alive():
        manager = FieldManager()
        tending_thread = threading.Thread(target=manager.tend_field, daemon=True)
        tending_thread.start()
    return "Resumed."

@app.route("/clear")
def clear():
    global manager, tending_thread
    wheat_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "wheat")
    pause_file = os.path.join(wheat_dir, "pause.txt")
    if os.path.exists(pause_file):
        os.remove(pause_file)
    manager.seeds = []
    if tending_thread and tending_thread.is_alive():
        tending_thread = None
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
    global manager, tending_thread
    try:
        new_config = request.get_data(as_text=True)
        json.loads(new_config)
        with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "config.json"), "w") as f:
            f.write(new_config)
        if tending_thread and tending_thread.is_alive():
            tending_thread = None
        manager = FieldManager()
        return jsonify({"message": "Config updated successfully. Restart sowing or resume to apply changes."})
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