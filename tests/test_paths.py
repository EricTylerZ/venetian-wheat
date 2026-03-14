"""Tests for wheat/paths.py — config loading and project path resolution."""

import json
import os
import pytest

from wheat.paths import (
    PROJECT_ROOT,
    DB_PATH,
    CONFIG_PATH,
    PROJECTS_PATH,
    load_config,
    load_projects,
    save_projects,
    load_project_config,
    project_dir,
)


class TestConstants:
    def test_project_root_exists(self):
        assert os.path.isdir(PROJECT_ROOT)

    def test_db_path_under_root(self):
        assert DB_PATH.startswith(PROJECT_ROOT)
        assert DB_PATH.endswith("wheat.db")

    def test_config_path_under_root(self):
        assert CONFIG_PATH.startswith(PROJECT_ROOT)
        assert CONFIG_PATH.endswith("config.json")

    def test_projects_path_under_root(self):
        assert PROJECTS_PATH.startswith(PROJECT_ROOT)
        assert PROJECTS_PATH.endswith("projects.json")


class TestLoadConfig:
    def test_returns_dict(self):
        config = load_config()
        assert isinstance(config, dict)

    def test_has_required_keys(self):
        config = load_config()
        # config.json should have at least these core keys
        assert "lifespan" in config
        assert "max_tokens" in config

    def test_reads_from_config_path(self, tmp_path, monkeypatch):
        fake_config = {"test_key": "test_value", "lifespan": 99}
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(fake_config))
        monkeypatch.setattr("wheat.paths.CONFIG_PATH", str(config_file))
        result = load_config()
        assert result == fake_config


class TestLoadProjects:
    def test_returns_dict(self):
        result = load_projects()
        assert isinstance(result, dict)

    def test_missing_file_returns_default(self, monkeypatch):
        monkeypatch.setattr("wheat.paths.PROJECTS_PATH", "/nonexistent/path.json")
        result = load_projects()
        assert result == {"default": {"name": "Default Field", "active": True}}

    def test_reads_from_projects_path(self, tmp_path, monkeypatch):
        fake_projects = {"proj1": {"name": "Test"}, "proj2": {"name": "Other"}}
        projects_file = tmp_path / "projects.json"
        projects_file.write_text(json.dumps(fake_projects))
        monkeypatch.setattr("wheat.paths.PROJECTS_PATH", str(projects_file))
        result = load_projects()
        assert result == fake_projects


class TestSaveProjects:
    def test_writes_json(self, tmp_path, monkeypatch):
        projects_file = tmp_path / "projects.json"
        monkeypatch.setattr("wheat.paths.PROJECTS_PATH", str(projects_file))
        data = {"p1": {"name": "Alpha"}, "p2": {"name": "Beta"}}
        save_projects(data)
        loaded = json.loads(projects_file.read_text())
        assert loaded == data

    def test_roundtrip(self, tmp_path, monkeypatch):
        projects_file = tmp_path / "projects.json"
        monkeypatch.setattr("wheat.paths.PROJECTS_PATH", str(projects_file))
        data = {"x": {"name": "X", "active": True}}
        save_projects(data)
        result = load_projects()
        assert result == data


class TestLoadProjectConfig:
    def test_base_config_for_unknown_project(self, tmp_path, monkeypatch):
        base = {"lifespan": 100, "max_tokens": 500, "llm_api": "test"}
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(base))
        monkeypatch.setattr("wheat.paths.CONFIG_PATH", str(config_file))
        monkeypatch.setattr("wheat.paths.PROJECTS_PATH", "/nonexistent.json")
        result = load_project_config("unknown_project")
        assert result["lifespan"] == 100
        assert result["max_tokens"] == 500

    def test_project_overrides_base(self, tmp_path, monkeypatch):
        base = {"lifespan": 100, "max_tokens": 500, "llm_api": "venice"}
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(base))
        monkeypatch.setattr("wheat.paths.CONFIG_PATH", str(config_file))

        projects = {"myproj": {"name": "My Project", "lifespan": 200, "max_tokens": 1000}}
        proj_file = tmp_path / "projects.json"
        proj_file.write_text(json.dumps(projects))
        monkeypatch.setattr("wheat.paths.PROJECTS_PATH", str(proj_file))

        result = load_project_config("myproj")
        assert result["lifespan"] == 200
        assert result["max_tokens"] == 1000
        assert result["llm_api"] == "venice"  # not overridden, keeps base

    def test_only_known_keys_overridden(self, tmp_path, monkeypatch):
        base = {"lifespan": 100, "max_tokens": 500}
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps(base))
        monkeypatch.setattr("wheat.paths.CONFIG_PATH", str(config_file))

        projects = {"p": {"name": "P", "unknown_key": "ignored", "lifespan": 999}}
        proj_file = tmp_path / "projects.json"
        proj_file.write_text(json.dumps(projects))
        monkeypatch.setattr("wheat.paths.PROJECTS_PATH", str(proj_file))

        result = load_project_config("p")
        assert result["lifespan"] == 999
        assert "unknown_key" not in result


class TestProjectDir:
    def test_default_project(self):
        result = project_dir("default")
        assert result == os.path.join(PROJECT_ROOT, "wheat")

    def test_named_project(self):
        result = project_dir("my_project")
        assert result == os.path.join(PROJECT_ROOT, "wheat", "projects", "my_project")

    def test_different_projects_different_dirs(self):
        assert project_dir("alpha") != project_dir("beta")
