import os
import json

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, "wheat.db")
CONFIG_PATH = os.path.join(PROJECT_ROOT, "config.json")
PROJECTS_PATH = os.path.join(PROJECT_ROOT, "projects.json")


def load_config():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def load_projects():
    """Load all project definitions from projects.json."""
    if not os.path.exists(PROJECTS_PATH):
        return {"default": {"name": "Default Field", "active": True}}
    with open(PROJECTS_PATH, "r") as f:
        return json.load(f)


def save_projects(projects):
    with open(PROJECTS_PATH, "w") as f:
        json.dump(projects, f, indent=2)


def load_project_config(project_id):
    """
    Load merged config for a project.
    Base config from config.json, overridden by project-specific settings.
    """
    base = load_config()
    projects = load_projects()
    project = projects.get(project_id, {})

    merged = {**base}
    for key in ("llm_api", "models", "seeds_per_run", "max_tokens", "timeout",
                "lifespan", "strategist_prompt", "coder_prompt", "rescue_prompt",
                "claude_code_model", "claude_code_timeout"):
        if key in project:
            merged[key] = project[key]

    return merged


def project_dir(project_id):
    """Get the base directory for a project's files."""
    if project_id == "default":
        return os.path.join(PROJECT_ROOT, "wheat")
    return os.path.join(PROJECT_ROOT, "wheat", "projects", project_id)
