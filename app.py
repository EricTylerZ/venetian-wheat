#app.py
from flask import Flask, request, render_template_string, jsonify, Response
from wheat.field_manager import FieldManager
import os
import json
import shutil
import threading
import time
import requests
from datetime import datetime

app = Flask(__name__)
manager = FieldManager()  # Single global instance, no auto-sowing
sowing_in_progress = False

def load_existing_run():
    wheat_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "wheat")
    run_dir = os.path.join(wheat_dir, "logs", "runs")
    if not os.path.exists(run_dir) or not os.listdir(run_dir):
        return None, None  # No runs exist
    run_files = [f for f in os.listdir(run_dir) if f.startswith("run_") and f.endswith(".txt")]
    if run_files:
        latest_run = max(run_files, key=lambda f: os.path.getmtime(os.path.join(run_dir, f)))
        latest_log = os.path.join(run_dir, latest_run)
        status_file = os.path.join(run_dir, f"field_status_{latest_run[4:-4]}.json")
        if os.path.exists(status_file):
            manager.log_path = latest_log
            manager.status_path = status_file
            if manager.log is None or manager.log.closed:
                manager.log = open(latest_log, "a", encoding="utf-8")
            with open(status_file, "r", encoding="utf-8") as f:
                status = json.load(f)
            manager.strains = [WheatStrain(info["task"], strain_id, manager.sower.coder_model) for strain_id, info in status.items()]
            for strain in manager.strains:
                strain.progress = status[strain.strain_id]
            return latest_log, status_file
    return None, None

@app.route("/")
def field_status():
    latest_log, status_file = load_existing_run()
    wheat_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "wheat")
    log = "Field not yet sowed."
    paused = os.path.exists(os.path.join(wheat_dir, "pause.txt"))
    status = {}
    if latest_log and os.path.exists(latest_log):
        with open(latest_log, "r", encoding="utf-8") as f:
            log = f.read()
    if status_file and os.path.exists(status_file):
        with open(status_file, "r", encoding="utf-8") as f:
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
        <h3>Field Log (Current Run)</h3>
        <pre id="log">{{ log }}</pre>
        <h3>Field Status</h3>
        <div id="processingStatus"></div>
        <table border="1" id="statusTable">
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
                    .then(data => alert(data.successful_strains));
            }
            function integrateStrains() {
                fetch('/integrate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'}
                }).then(response => response.json())
                  .then(data => alert(data.message));
            }
            const eventSource = new EventSource('/stream');
            eventSource.onmessage = function(event) {
                const data = JSON.parse(event.data);
                document.getElementById('log').innerText = data.log;
                const table = document.getElementById('statusTable');
                table.innerHTML = '<tr><th>Strain</th><th>Task</th><th>Status</th><th>Output</th></tr>';
                Object.entries(data.status).forEach(([strain_id, info]) => {
                    const row = table.insertRow();
                    row.insertCell().innerText = strain_id;
                    row.insertCell().innerText = info.task;
                    row.insertCell().innerText = info.status;
                    row.insertCell().innerHTML = info.output.join('<br>');
                });
                document.getElementById('processingStatus').innerText = data.complete ? 'Processing complete' : 'Processing strains...';
            };
            eventSource.onerror = function() {
                console.log('SSE error - reconnecting...');
            };
        </script>
    """, log=log, status=status, paused=paused)

@app.route("/sow", methods=["POST"])
def sow():
    global sowing_in_progress, manager
    if sowing_in_progress:
        return jsonify({"message": "Sowing already in progress."}), 400
    sowing_in_progress = True
    try:
        data = request.get_json() or {}
        guidance = data.get("guidance")
        manager = FieldManager()
        manager.sow_field(guidance)
        manager.tend_field()
        return jsonify({"message": f"Seeds sowed with guidance: '{guidance or 'None (Venice AI will propose)'}'"})
    finally:
        sowing_in_progress = False

@app.route("/stream")
def stream():
    def event_stream():
        wheat_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "wheat")
        while True:
            latest_log, status_file = load_existing_run()
            log = "Field not yet sowed."
            status = {}
            if latest_log and os.path.exists(latest_log):
                with open(latest_log, "r", encoding="utf-8") as f:
                    log = f.read()
            if status_file and os.path.exists(status_file):
                with open(status_file, "r", encoding="utf-8") as f:
                    status = json.load(f)
            complete = all(s.progress["status"] in ["Fruitful", "Barren"] for s in manager.strains) if manager.strains else True
            yield f"data: {json.dumps({'log': log, 'status': status, 'complete': complete})}\n\n"
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
    return "Resumed."

@app.route("/clear")
def clear():
    global manager
    wheat_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "wheat")
    for file in ["pause.txt"]:
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
    os.makedirs(os.path.join(strains_dir, "generated"), exist_ok=True)
    os.makedirs(os.path.join(logs_dir, "runs"), exist_ok=True)
    os.makedirs(os.path.join(logs_dir, "sunshine"), exist_ok=True)
    manager.strains = []  # Clear strains without creating a new manager
    manager.log_path = None
    manager.status_path = None
    if manager.log and not manager.log.closed:
        manager.log.close()
    manager.log = None
    return "Cleared all experiments."

@app.route("/success")
def show_successful_strains():
    wheat_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "wheat")
    status_file = manager.status_path if manager and hasattr(manager, 'status_path') else None
    summary = "No successful strains found."
    if status_file and os.path.exists(status_file):
        with open(status_file, "r", encoding="utf-8") as f:
            status = json.load(f)
        successful = []
        for strain_id, info in status.items():
            if info["status"] == "Fruitful" and info["output"]:
                try:
                    code_ref = info["output"][-1].split("[Code: ")[1].rstrip("]")
                    successful.append(f"Strain {strain_id}: {info['task']} - Code: {code_ref}")
                except IndexError:
                    successful.append(f"Strain {strain_id}: {info['task']} - Code: Not available")
        summary = "\n".join(successful) if successful else summary
    return jsonify({"successful_strains": summary})

@app.route("/integrate", methods=["POST"])
def integrate_successful_strains():
    wheat_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "wheat")
    success_dir = os.path.join(wheat_dir, "successful_strains")
    helpers_dir = os.path.join(wheat_dir, "helpers")
    status_file = manager.status_path if manager and hasattr(manager, 'status_path') else None
    integrated = []
    integrated_info = {}

    if status_file and os.path.exists(status_file):
        with open(status_file, "r", encoding="utf-8") as f:
            status = json.load(f)
        os.makedirs(success_dir, exist_ok=True)
        os.makedirs(helpers_dir, exist_ok=True)

        for strain_id, info in status.items():
            if info["status"] == "Fruitful":
                try:
                    code_file = info["output"][-1].split("[Code: ")[1].rstrip("]") if info["output"] else info.get("code_file", "")
                    if not code_file and info["code"]:
                        code_file = os.path.join(wheat_dir, "strains", "generated", f"wheat_{strain_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py")
                        with open(code_file, "w", encoding="utf-8") as f:
                            f.write(info["code"])
                    if os.path.exists(code_file):
                        filename = f"strain_{strain_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
                        dest_file = os.path.join(success_dir, filename)
                        shutil.copy(code_file, dest_file)
                        helper_file = os.path.join(helpers_dir, filename)
                        shutil.copy(code_file, helper_file)
                        integrated.append(filename)
                        with open(code_file, "r", encoding="utf-8") as f:
                            content = f.read()
                            func_match = re.search(r'def (\w+)\((.*?)\):', content)
                            func_name = func_match.group(1) if func_match else "unknown_function"
                            params = func_match.group(2).strip() if func_match else "unknown"
                            purpose_match = re.search(r'"""(.*?)"""', content, re.DOTALL)
                            purpose = purpose_match.group(1).strip() if purpose_match else "Unknown purpose"
                        integrated_info[filename] = {"function": func_name, "purpose": purpose, "parameters": params}
                except (IndexError, KeyError):
                    continue

        with open(os.path.join(helpers_dir, "script_registry.json"), "w", encoding="utf-8") as f:
            json.dump(integrated_info, f, indent=2)

    return jsonify({"integrated": integrated, "message": f"Integrated {len(integrated)} successful strains into wheat/helpers/."})

if __name__ == "__main__":
    app.run(port=5001)