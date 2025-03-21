#wheat/analyze_logs.py
import os
import json
import csv
import requests
from datetime import datetime

def consolidate_logs():
    log_dir = os.path.join(os.path.dirname(__file__), "logs")
    all_files_content = ""
    file_list = []
    for filename in os.listdir(log_dir):
        if filename.endswith(".py"):
            file_path = os.path.join(log_dir, filename)
            with open(file_path, "r", encoding="utf-8") as f:
                content = f.read()
            all_files_content += f"# {file_path}\n{content}\n\n"
            file_list.append(file_path)
    return all_files_content, file_list

def analyze_with_llm(content):
    with open(os.path.join(os.path.dirname(__file__), "config.json"), "r") as f:
        config = json.load(f)
    headers = {"Authorization": f"Bearer {os.environ.get('VENICE_API_KEY')}", "Content-Type": "application/json"}
    prompt = f"Analyze these Python scripts and determine their purpose and success (Fruitful if they have valid syntax and a passing unittest, Barren otherwise). Return a CSV with columns: File, Purpose, Status.\n{content}"
    payload = {
        "model": config["default_coder_model"],
        "messages": [{"role": "system", "content": prompt}],
        "max_tokens": config["max_tokens"]
    }
    retries = 3
    for attempt in range(retries):
        try:
            response = requests.post(config["venice_api_url"], headers=headers, json=payload, timeout=config["timeout"])
            if response.status_code == 429:
                time.sleep(10 * (attempt + 1))
                continue
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
        except requests.RequestException as e:
            if attempt == retries - 1:
                return f"Error: {str(e)}"
            time.sleep(10 * (attempt + 1))

def save_to_csv(csv_content, output_file):
    with open(output_file, "w", encoding="utf-8", newline="") as f:
        f.write(csv_content)

if __name__ == "__main__":
    content, files = consolidate_logs()
    print(f"Found {len(files)} files to analyze.")
    csv_content = analyze_with_llm(content)
    output_file = os.path.join(os.path.dirname(__file__), f"strain_analysis_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv")
    save_to_csv(csv_content, output_file)
    print(f"Analysis saved to {output_file}")