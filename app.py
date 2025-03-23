#app.py
from flask import Flask, request, render_template_string, jsonify, Response
from wheat.field_manager import FieldManager  # Only import FieldManager
import sqlite3
import os
import json
import threading
from datetime import datetime

app = Flask(__name__)
manager = FieldManager()
sowing_in_progress = False
tending_thread = None
db_lock = threading.Lock()  # Moved back to app.py

def init_db():
    with db_lock:
        conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.realpath(__file__)), "wheat.db"))
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            log TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS strains (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER,
            strain_id TEXT,
            task TEXT,
            status TEXT,
            output TEXT,
            code_file TEXT,
            test_result TEXT,
            FOREIGN KEY (run_id) REFERENCES runs(id)
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS api_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            strain_id INTEGER,
            timestamp TEXT,
            request TEXT,
            response TEXT,
            FOREIGN KEY (strain_id) REFERENCES strains(id)
        )''')
        conn.commit()
        conn.close()

init_db()

def get_latest_run():
    with db_lock:
        conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.realpath(__file__)), "wheat.db"))
        c = conn.cursor()
        c.execute("SELECT id, timestamp, log FROM runs ORDER BY id DESC LIMIT 1")
        run = c.fetchone()
        if run:
            run_id, timestamp, log = run
            c.execute("SELECT strain_id, task, status, output, code_file, test_result FROM strains WHERE run_id = ?", (run_id,))
            strains = c.fetchall()
            manager.strains = [manager.create_strain(row[0], row[1], row[2], row[3], row[4], row[5]) for row in strains]
            return log, {"timestamp": timestamp, "strains": {row[0]: {"task": row[1], "status": row[2], "output": json.loads(row[3]) if row[3] else [], "code_file": row[4], "test_result": row[5]} for row in strains}}
        conn.close()
        return None, None

@app.route("/")
def field_status():
    log, status_data = get_latest_run()
    wheat_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "wheat")
    log = log or "Field not yet sowed."
    paused = os.path.exists(os.path.join(wheat_dir, "pause.txt"))
    status = status_data["strains"] if status_data else {}

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
    global sowing_in_progress, tending_thread
    if sowing_in_progress:
        return jsonify({"message": "Sowing already in progress."}), 400
    sowing_in_progress = True
    try:
        data = request.get_json() or {}
        guidance = data.get("guidance")
        manager = FieldManager()
        manager.sow_field(guidance)
        tending_thread = threading.Thread(target=manager.tend_field)
        tending_thread.start()
        return jsonify({"message": f"Seeds sowed with guidance: '{guidance or 'None (Venice AI will propose)'}'"})
    finally:
        sowing_in_progress = False

@app.route("/stream")
def stream():
    def event_stream():
        while True:
            log, status_data = get_latest_run()
            log = log or "Field not yet sowed."
            status = status_data["strains"] if status_data else {}
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
    global manager, tending_thread
    wheat_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "wheat")
    pause_file = os.path.join(wheat_dir, "pause.txt")
    if os.path.exists(pause_file):
        os.remove(pause_file)
    manager.strains = []
    if tending_thread and tending_thread.is_alive():
        tending_thread = None
    return "Cleared experiments."

@app.route("/success")
def show_successful_strains():
    status_file = manager.status_path if manager and hasattr(manager, 'status_path') else None
    summary = "No successful strains found."
    if status_file and os.path.exists(status_file):
        with open(status_file, "r", encoding="utf-8") as f:
            status = json.load(f)
        successful = [f"Strain {strain_id}: {info['task']} - {info['output'][-1]}" for strain_id, info in status.items() if info["status"] == "Fruitful" and info["output"]]
        summary = "\n".join(successful) if successful else summary
    return jsonify({"successful_strains": summary})

@app.route("/integrate", methods=["POST"])
def integrate_successful_strains():
    wheat_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "wheat")
    success_dir = os.path.join(wheat_dir, "successful_strains")
    helpers_dir = os.path.join(wheat_dir, "helpers")
    with db_lock:
        conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.realpath(__file__)), "wheat.db"))
        c = conn.cursor()
        c.execute("SELECT id FROM runs ORDER BY id DESC LIMIT 1")
        run_id = c.fetchone()[0] if c.fetchone() else None
        integrated = []
        integrated_info = {}

        if run_id:
            c.execute("SELECT strain_id, task, status, code_file FROM strains WHERE run_id = ? AND status = 'Fruitful'", (run_id,))
            strains = c.fetchall()
            os.makedirs(success_dir, exist_ok=True)
            os.makedirs(helpers_dir, exist_ok=True)

            for strain_id, task, status, code_file in strains:
                if code_file and os.path.exists(code_file):
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

            with open(os.path.join(helpers_dir, "script_registry.json"), "w", encoding="utf-8") as f:
                json.dump(integrated_info, f, indent=2)

        conn.close()
    return jsonify({"integrated": integrated, "message": f"Integrated {len(integrated)} successful strains into wheat/helpers/."})

if __name__ == "__main__":
    app.run(port=5001)