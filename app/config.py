import json
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger("config")

BASE_DIR = Path(__file__).resolve().parent.parent

# 1. Configurable Canvas Base URL
CANVAS_BASE_URL = os.environ.get("CANVAS_BASE_URL", "https://canvas.instructure.com").rstrip("/")


def get_config_dir() -> Path:
    """Return standard user configuration directory with safe permissions (ISO 27001 8.24 / SOC 2 CC6.1)."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        base = Path(xdg) if xdg else Path.home() / ".config"
    config_dir = base / "canvasdl"
    try:
        config_dir.mkdir(parents=True, exist_ok=True)
        if os.name != "nt":
            config_dir.chmod(0o700)
    except OSError as e:
        logger.debug(f"No se pudieron ajustar permisos 0700 en {config_dir}: {e}")
    return config_dir


CONFIG_DIR = get_config_dir()
USER_TOKEN_FILE = CONFIG_DIR / "canvas_token.txt"
LEGACY_TOKEN_FILE = BASE_DIR / "canvas_token.txt"

# Preferred token file (legacy fallback maintained for existing local clones)
TOKEN_FILE = LEGACY_TOKEN_FILE if LEGACY_TOKEN_FILE.exists() else USER_TOKEN_FILE
SESSION_FILE = BASE_DIR / "session.json" if (BASE_DIR / "session.json").exists() else (CONFIG_DIR / "session.json")
SETTINGS_FILE = BASE_DIR / "settings.json" if (BASE_DIR / "settings.json").exists() else (CONFIG_DIR / "settings.json")

DEFAULT_DOWNLOAD_DIR = Path.home() / "Downloads" / "CanvasDL"


def get_token() -> Optional[str]:
    """Retrieve Canvas API token prioritizing environment variables, then secure files."""
    # Priority 1: Environment variable (SOC 2 best practice: stateless & non-persisted)
    env_token = os.environ.get("CANVAS_API_TOKEN") or os.environ.get("CANVAS_TOKEN")
    if env_token and env_token.strip():
        return env_token.strip()

    # Priority 2: Secure user config directory
    if USER_TOKEN_FILE.exists():
        try:
            token = USER_TOKEN_FILE.read_text(encoding="utf-8").strip()
            if token:
                return token
        except Exception as e:
            logger.warning(f"Error leyendo {USER_TOKEN_FILE}: {e}")

    # Priority 3: Legacy local file for local workspace
    if LEGACY_TOKEN_FILE.exists():
        try:
            token = LEGACY_TOKEN_FILE.read_text(encoding="utf-8").strip()
            if token:
                return token
        except Exception as e:
            logger.warning(f"Error leyendo {LEGACY_TOKEN_FILE}: {e}")

    return None


def save_token(token: str) -> None:
    """Save token to secure user location with restrictive permissions (0600 on POSIX)."""
    clean_token = token.strip()
    target_file = USER_TOKEN_FILE
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text(clean_token, encoding="utf-8")
    if os.name != "nt":
        try:
            target_file.chmod(0o600)
        except OSError:
            pass

    # Also keep legacy file in sync if it exists in local repo
    if LEGACY_TOKEN_FILE.exists():
        try:
            LEGACY_TOKEN_FILE.write_text(clean_token, encoding="utf-8")
            if os.name != "nt":
                LEGACY_TOKEN_FILE.chmod(0o600)
        except OSError:
            pass


def get_settings() -> dict:
    defaults = {
        "download_dir": str(DEFAULT_DOWNLOAD_DIR),
        "canvas_url": CANVAS_BASE_URL,
        "max_concurrent_downloads": 4,
        "auto_open_folder": False,
        "organize_by": "modules",  # "modules" o "folders"
    }
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                defaults.update(saved)
        except Exception:
            pass
    return defaults


def save_settings(new_settings: dict) -> dict:
    current = get_settings()
    current.update(new_settings)
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(current, f, indent=2, ensure_ascii=False)
    return current


def get_download_path() -> Path:
    settings = get_settings()
    path = Path(settings.get("download_dir", DEFAULT_DOWNLOAD_DIR)).expanduser().resolve()
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return path
