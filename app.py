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
    wheat_dir = os.path.join(os.path.dirname(__file__), "wheat")
    run_dir = os.path.join(wheat_dir, "logs", "runs")
    latest_log = max([os.path.join(run_dir, f) for f in os.listdir(run_dir) if f.startswith("run_")] or [], default=None, key=os.path.getmtime) if os.path.exists(run_dir) else None
    log = "Field not yet sowed."
    status_path = os.path.join(wheat_dir, "field_status.json")
    paused = os.path.exists(os.path.join(wheat_dir, "pause.txt"))
    status = {}
    if latest_log:
        with open(latest_log, "r", encoding="utf-8") as f:
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
        <button onclick="showSuccess()">Show Successful Strains</button>
        <button onclick="integrateStrains()">Integrate Successful Strains</button>
        <h3>Field Log (Latest Run)</h3>
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
                setTimeout(() => window.location.reload(), 2000); // Refresh after sowing
            }
            async function showSuccess() {
                const response = await fetch('/success');
                const data = await response.json();
                alert(data.successful_strains);
            }
            async function integrateStrains() {
                const response = await fetch('/integrate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'}
                });
                const data = await response.json();
                alert(data.message);
            }
            if (!paused) {
                setInterval(() => {
                    cycle += 16;
                    document.getElementById('cycle').innerText = cycle;
                    window.location.reload();
                }, 16000);
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
    for file in ["field_status.json", "pause.txt"]:
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
    os.makedirs(os.path.join(logs_dir, "runs"), exist_ok=True)
    manager.strains = []
    manager.sow_field()
    return "Cleared all experiments."

@app.route("/success")
def show_successful_strains():
    status_path = os.path.join(os.path.dirname(__file__), "wheat", "field_status.json")
    summary = "No successful strains found."
    if os.path.exists(status_path):
        with open(status_path, "r", encoding="utf-8") as f:
            status = json.load(f)
        successful = [
            f"Strain {strain_id}: {info['task']} - Code: {info['output'][-1].split('[Code: ')[1].rstrip(']')}"
            for strain_id, info in status.items() if info["status"] == "Fruitful"
        ]
        summary = "\n".join(successful) if successful else summary
    return jsonify({"successful_strains": summary})

@app.route("/integrate", methods=["POST"])
def integrate_successful_strains():
    wheat_dir = os.path.join(os.path.dirname(__file__), "wheat")
    success_dir = os.path.join(wheat_dir, "successful_strains")
    helpers_dir = os.path.join(wheat_dir, "helpers")
    status_path = os.path.join(wheat_dir, "field_status.json")
    integrated = []
    integrated_info = {}

    if os.path.exists(status_path):
        with open(status_path, "r", encoding="utf-8") as f:
            status = json.load(f)
        os.makedirs(success_dir, exist_ok=True)
        os.makedirs(helpers_dir, exist_ok=True)

        for strain_id, info in status.items():
            if info["status"] == "Fruitful" and "Code:" in info["output"][-1]:
                code_file = info["output"][-1].split("[Code: ")[1].rstrip("]")
                if os.path.exists(code_file):
                    filename = f"strain_{strain_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
                    dest_file = os.path.join(success_dir, filename)
                    shutil.copy(code_file, dest_file)
                    helper_file = os.path.join(helpers_dir, filename)
                    shutil.copy(code_file, helper_file)
                    integrated.append(filename)
                    # Extract function name and purpose (simplified)
                    with open(code_file, "r", encoding="utf-8") as f:
                        content = f.read()
                        func_match = re.search(r'def (\w+)\(', content)
                        func_name = func_match.group(1) if func_match else "unknown_function"
                        purpose_match = re.search(r'"""(.*?)"""', content, re.DOTALL)
                        purpose = purpose_match.group(1).strip() if purpose_match else "Unknown purpose"
                    integrated_info[filename] = {"function": func_name, "purpose": purpose, "parameters": "TODO: Parse"}

        # Save integration info
        with open(os.path.join(helpers_dir, "integrated.json"), "w", encoding="utf-8") as f:
            json.dump(integrated_info, f, indent=2)

    return jsonify({"integrated": integrated, "message": f"Integrated {len(integrated)} successful strains into wheat/helpers/."})

if __name__ == "__main__":
    app.run(port=5001)