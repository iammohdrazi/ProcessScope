"""
ProcessScope — Configuration loader.

Loads configuration from (in priority order):
1. CLI arguments
2. Environment variables (PROCESSSCOPE_*)
3. /etc/processscope/processscope.yaml
4. Built-in defaults
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


# ── Configuration Models ─────────────────────────────────────────────

class ServerConfig(BaseModel):
    """HTTP/WebSocket server configuration."""
    host: str = "0.0.0.0"
    port: int = 9876
    workers: int = 1
    cors_origins: list[str] = ["*"]


class TelemetryConfig(BaseModel):
    """Telemetry collection configuration."""
    poll_interval_ms: int = 1000
    buffer_size: int = 10000
    collectors: list[str] = [
        "cpu", "memory", "thread", "network", "filesystem", "syscall", "hardware"
    ]
    enable_ebpf: bool = False


class LoggingConfig(BaseModel):
    """Logging configuration — dual logging: syslog + file."""
    level: str = "INFO"
    file_path: str = "/var/log/processscope"
    syslog_enabled: bool = True
    syslog_facility: str = "daemon"
    syslog_identifier: str = "processscope"
    json_format: bool = True
    max_file_size_mb: int = 50
    backup_count: int = 7


class StorageConfig(BaseModel):
    """Data storage configuration."""
    db_path: str = "/var/lib/processscope/db/processscope.db"
    session_path: str = "/var/lib/processscope/sessions"
    retention_days: int = 7
    max_db_size_mb: int = 500


class SecurityConfig(BaseModel):
    """Security configuration."""
    read_only_mode: bool = False
    require_auth: bool = False
    api_key: str = ""
    allowed_pids: list[int] = []
    denied_pids: list[int] = []


class AppConfig(BaseSettings):
    """
    Root application configuration.

    Supports loading from YAML file + environment variables (PROCESSSCOPE_ prefix).
    """
    server: ServerConfig = Field(default_factory=ServerConfig)
    telemetry: TelemetryConfig = Field(default_factory=TelemetryConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    dev_mode: bool = False
    plugin_dir: str = "/opt/processscope/plugins"

    model_config = {
        "env_prefix": "PROCESSSCOPE_",
        "env_nested_delimiter": "__",
    }


# ── Configuration Paths ──────────────────────────────────────────────

DEFAULT_CONFIG_PATHS = [
    Path("/etc/processscope/processscope.yaml"),
    Path("/etc/processscope/processscope.yml"),
    Path.home() / ".config" / "processscope" / "processscope.yaml",
    Path("configs/processscope.yaml"),  # Development fallback
]


# ── Loader ────────────────────────────────────────────────────────────

def load_config(config_path: str | Path | None = None) -> AppConfig:
    """
    Load application configuration.

    Priority:
    1. Explicit config_path argument
    2. PROCESSSCOPE_CONFIG_FILE environment variable
    3. Default paths (see DEFAULT_CONFIG_PATHS)
    4. Built-in defaults
    """
    yaml_data: dict[str, Any] = {}

    # Determine config file path
    if config_path:
        path = Path(config_path)
    elif env_path := os.environ.get("PROCESSSCOPE_CONFIG_FILE"):
        path = Path(env_path)
    else:
        path = _find_config_file()

    # Load YAML if found
    if path and path.exists():
        try:
            with open(path) as f:
                yaml_data = yaml.safe_load(f) or {}
        except (yaml.YAMLError, OSError) as e:
            # Can't use our logger here (not initialized yet), use stderr
            import sys
            print(f"[processscope] WARNING: Failed to load config from {path}: {e}", file=sys.stderr)

    # Build config: YAML values → then env overrides via pydantic-settings
    return AppConfig(**yaml_data)


def _find_config_file() -> Path | None:
    """Search default paths for a config file."""
    for path in DEFAULT_CONFIG_PATHS:
        if path.exists():
            return path
    return None


def write_default_config(path: Path) -> None:
    """Write the default configuration to a YAML file."""
    config = AppConfig()
    data = config.model_dump()

    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, indent=2)
