#app.py
from flask import Flask, request, render_template_string, jsonify
from wheat.field_manager import FieldManager
import os
import json
import shutil
import threading
import time
import requests
from datetime import datetime

app = Flask(__name__)
manager = FieldManager()
sowing_in_progress = False

def run_field_manager():
    while True:
        if not os.path.exists(os.path.join(os.path.dirname(__file__), "wheat", "pause.txt")) and not sowing_in_progress:
            manager.tend_field()
        time.sleep(60)

threading.Thread(target=run_field_manager, daemon=True).start()

@app.route("/")
def field_status():
    log_path = os.path.join(os.path.dirname(__file__), "wheat", "field_log.txt")
    status_path = os.path.join(os.path.dirname(__file__), "wheat", "field_status.json")
    paused = os.path.exists(os.path.join(os.path.dirname(__file__), "wheat", "pause.txt"))
    log = "Field not yet sowed."
    status = {}
    if os.path.exists(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            log = f.read()
    if os.path.exists(status_path):
        with open(status_path, "r", encoding="utf-8") as f:
            status = json.load(f)

    return render_template_string("""
        <h2>Venetian Wheat Field</h2>
        <form id="sowForm" onsubmit="sowSeeds(event)">
            <textarea name="guidance" rows="4" cols="50" placeholder="Sow guidance (e.g., 'Improve strain logging')—leave blank for Venice AI to propose"></textarea><br>
            <input type="submit" value="Sow Seeds">
        </form>
        <button onclick="fetch('/pause')">Pause</button>
        <button onclick="fetch('/resume')">Resume</button>
        <button onclick="fetch('/clear')">Clear Experiments</button>
        <button onclick="fetch('/success')">Show Successful Strains</button>
        <button onclick="fetch('/integrate')">Integrate Successful Strains</button>
        <h3>Field Log</h3>
        <pre>{{ log }}</pre>
        <h3>Field Status</h3>
        <div id="timer">Cycle: <span id="cycle">0</span>s</div>
        <table border="1">
            <tr><th>Strain</th><th>Task</th><th>Status</th><th>Output</th></tr>
            {% for strain_id, info in status.items() %}
                <tr>
                    <td>{{ strain_id }}</td>
                    <td>{{ info.task }}</td>
                    <td>{{ info.status }}</td>
                    <td>{{ info.output|join('<br>') }}</td>
                </tr>
            {% endfor %}
        </table>
        <script>
            let cycle = 0;
            let paused = {{ 'true' if paused else 'false' }};
            async function sowSeeds(event) {
                event.preventDefault();
                const form = document.getElementById('sowForm');
                const guidance = form.querySelector('textarea').value.trim();
                const response = await fetch('/sow', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({guidance: guidance || null})
                });
                const result = await response.json();
                alert(result.message);
            }
            if (!paused) {
                setInterval(() => {
                    cycle += 5;
                    document.getElementById('cycle').innerText = cycle;
                    window.location.reload();
                }, 5000);
            }
        </script>
    """, log=log, status=status, paused=paused)

@app.route("/sow", methods=["POST"])
def sow():
    global sowing_in_progress
    if sowing_in_progress:
        return jsonify({"message": "Sowing already in progress."}), 400
    sowing_in_progress = True
    try:
        data = request.get_json() or {}
        guidance = data.get("guidance")
        manager.sow_field(guidance)
        manager.tend_field()
        return jsonify({"message": f"Seeds sowed with guidance: '{guidance or 'None (Venice AI will propose)'}'"})
    finally:
        sowing_in_progress = False

@app.route("/pause")
def pause():
    open(os.path.join(os.path.dirname(__file__), "wheat", "pause.txt"), "w").close()
    return "Paused."

@app.route("/resume")
def resume():
    pause_file = os.path.join(os.path.dirname(__file__), "wheat", "pause.txt")
    if os.path.exists(pause_file):
        os.remove(pause_file)
    return "Resumed."

@app.route("/clear")
def clear():
    wheat_dir = os.path.join(os.path.dirname(__file__), "wheat")
    for file in ["field_log.txt", "field_status.json", "pause.txt"]:
        file_path = os.path.join(wheat_dir, file)
        if os.path.exists(file_path):
            os.remove(file_path)
    strains_dir = os.path.join(wheat_dir, "strains")
    logs_dir = os.path.join(wheat_dir, "logs")
    success_dir = os.path.join(wheat_dir, "successful_strains")
    for dir_path in [strains_dir, logs_dir, success_dir]:
        if os.path.exists(dir_path):
            shutil.rmtree(dir_path)
    os.makedirs(strains_dir, exist_ok=True)
    os.makedirs(logs_dir, exist_ok=True)
    os.makedirs(success_dir, exist_ok=True)
    manager.strains = []
    manager.sow_field()
    return "Cleared all experiments."

@app.route("/success")
def show_successful_strains():
    log_path = os.path.join(os.path.dirname(__file__), "wheat", "field_log.txt")
    log_content = open(log_path, "r", encoding="utf-8").read() if os.path.exists(log_path) else ""
    with open(os.path.join(os.path.dirname(__file__), "wheat", "config.json"), "r") as f:
        config = json.load(f)
    headers = {"Authorization": f"Bearer {os.environ.get('VENICE_API_KEY')}", "Content-Type": "application/json"}
    prompt = f"Summarize the successful (Fruitful) strains from this log, identifying strain ID, task, and code file location:\n{log_content}"
    payload = {
        "model": config["default_coder_model"],
        "messages": [{"role": "system", "content": prompt}],
        "max_tokens": config["max_tokens"]
    }
    try:
        response = requests.post(config["venice_api_url"], headers=headers, json=payload, timeout=config["timeout"])
        response.raise_for_status()
        summary = response.json()["choices"][0]["message"]["content"].strip()
        success_dir = os.path.join(os.path.dirname(__file__), "wheat", "successful_strains")
        os.makedirs(success_dir, exist_ok=True)
        status_path = os.path.join(os.path.dirname(__file__), "wheat", "field_status.json")
        if os.path.exists(status_path):
            with open(status_path, "r", encoding="utf-8") as f:
                status = json.load(f)
            for strain_id, info in status.items():
                if info["status"] == "Fruitful" and "Code:" in info["output"][-1]:
                    code_file = info["output"][-1].split("[Code: ")[1].rstrip("]")
                    if os.path.exists(code_file):
                        dest_file = os.path.join(success_dir, f"strain_{strain_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py")
                        shutil.copy(code_file, dest_file)
                        info["output"].append(f"[Saved to: {dest_file}]")
            with open(status_path, "w", encoding="utf-8") as f:
                json.dump(status, f, indent=2)
    except requests.RequestException as e:
        summary = f"Failed to summarize: {str(e)}"
    return jsonify({"successful_strains": summary})

@app.route("/integrate", methods=["POST"])
def integrate_successful_strains():
    success_dir = os.path.join(os.path.dirname(__file__), "wheat", "successful_strains")
    integrated = []
    if os.path.exists(success_dir):
        for filename in os.listdir(success_dir):
            if filename.endswith(".py"):
                src_path = os.path.join(success_dir, filename)
                dest_path = os.path.join(os.path.dirname(__file__), "wheat", "helpers", filename)
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                shutil.copy(src_path, dest_path)
                integrated.append(filename)
    return jsonify({"integrated": integrated, "message": f"Integrated {len(integrated)} successful strains into wheat/helpers/."})

if __name__ == "__main__":
    app.run(port=5001)