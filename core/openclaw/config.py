"""配置加载与管理"""
from __future__ import annotations
import json
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any


CONFIG_BASE = Path(os.environ.get("OPENCLAW_BASE", "/opt/openclaw"))
CONFIG_FILE = CONFIG_BASE / "instance" / "config" / "openclaw.json"
WORKERS_FILE = CONFIG_BASE / "instance" / "config" / "remote-workers.json"
ROLES_DIR = CONFIG_BASE / "instance" / "config" / "roles"
WORKSPACE = CONFIG_BASE / "instance" / "workspace"
LOGS_DIR = CONFIG_BASE / "instance" / "logs"


@dataclass
class ModelConfig:
    provider: str
    base_url: str
    model_name: str
    api_key_env: str
    max_tokens: int = 4096

    @property
    def api_key(self) -> str:
        return os.environ.get(self.api_key_env, "")


@dataclass
class RoleConfig:
    name: str
    enabled: bool
    prompt_file: str
    model: str
    max_retries: int = 2
    timeout_seconds: int = 60
    allowed_tools: list[str] = field(default_factory=list)
    sandbox: bool = False
    _prompt_text: str | None = field(default=None, repr=False)

    @property
    def prompt(self) -> str:
        if self._prompt_text is None:
            path = ROLES_DIR / Path(self.prompt_file).name
            self._prompt_text = path.read_text(encoding="utf-8") if path.exists() else ""
        return self._prompt_text


@dataclass
class RemoteWorker:
    name: str
    enabled: bool
    base_url: str
    auth_token_env: str
    capabilities: list[str] = field(default_factory=list)
    max_concurrent: int = 3
    timeout: int = 300

    @property
    def auth_token(self) -> str:
        return os.environ.get(self.auth_token_env, "")


class Config:
    """全局配置单例"""

    def __init__(self):
        self._raw: dict[str, Any] = {}
        self.models: dict[str, ModelConfig] = {}
        self.roles: dict[str, RoleConfig] = {}
        self.workers: dict[str, RemoteWorker] = {}
        self.telegram: dict[str, Any] = {}
        self.pipeline: dict[str, Any] = {}

    def load(self, config_path: Path | None = None) -> "Config":
        path = config_path or CONFIG_FILE
        with open(path, encoding="utf-8") as f:
            self._raw = json.load(f)

        # 模型配置
        for name, m in self._raw.get("models", {}).items():
            self.models[name] = ModelConfig(
                provider=m["provider"],
                base_url=m["base_url"],
                model_name=m["model_name"],
                api_key_env=m["api_key_env"],
                max_tokens=m.get("max_tokens", 4096),
            )

        # 角色配置
        for name, r in self._raw.get("roles", {}).items():
            self.roles[name] = RoleConfig(
                name=name,
                enabled=r.get("enabled", True),
                prompt_file=r["prompt_file"],
                model=r["model"],
                max_retries=r.get("max_retries", 2),
                timeout_seconds=r.get("timeout_seconds", 60),
                allowed_tools=r.get("allowed_tools", []),
                sandbox=r.get("sandbox", False),
            )

        # Telegram / Pipeline
        self.telegram = self._raw.get("telegram", {})
        self.pipeline = self._raw.get("pipeline", {})

        # 远程 worker
        self._load_workers()
        return self

    def _load_workers(self):
        if not WORKERS_FILE.exists():
            return
        with open(WORKERS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        for name, w in data.get("workers", {}).items():
            self.workers[name] = RemoteWorker(
                name=name,
                enabled=w.get("enabled", False),
                base_url=w.get("base_url", ""),
                auth_token_env=w.get("auth_token_env", ""),
                capabilities=w.get("capabilities", []),
                max_concurrent=w.get("resource_limits", {}).get("max_concurrent_tasks", 3),
                timeout=w.get("resource_limits", {}).get("timeout_seconds", 300),
            )

    def get_model(self, name: str) -> ModelConfig:
        if name not in self.models:
            raise ValueError(f"未知模型: {name}，可用: {list(self.models.keys())}")
        return self.models[name]

    def get_active_workers(self) -> list[RemoteWorker]:
        return [w for w in self.workers.values() if w.enabled]


# 全局配置实例
config = Config()
