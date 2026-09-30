"""Application settings: secrets in the OS keyring, preferences in local JSON."""
import json
from pathlib import Path
from typing import Any, Optional

import keyring
import keyring.errors

APP_NAME = "MergeLY"
CONFIG_DIR = Path.home() / ".mergely"
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULT_PREFS: dict[str, Any] = {
    "default_provider": "auto",
    "gitlab_url": "https://gitlab.com",
    "jira_url": "",
    "jira_email": "",
    "notifier_type": "google_chat",
    "openai_model": "gpt-4o",
}

# Secrets never touch the JSON prefs file; they live only in the OS keyring.
SECRET_KEYS = (
    "gitlab_token",
    "github_token",
    "jira_token",
    "openai_api_key",
    "chat_webhook_url",
)


class ConfigManager:
    def __init__(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self._prefs = self._load_prefs()

    def _load_prefs(self) -> dict[str, Any]:
        data: dict[str, Any] = {}
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text())
            except (json.JSONDecodeError, OSError):
                data = {}
        return {**DEFAULT_PREFS, **data}

    def save_prefs(self) -> None:
        CONFIG_FILE.write_text(json.dumps(self._prefs, indent=2))

    def get_pref(self, key: str, default: Any = None) -> Any:
        return self._prefs.get(key, default)

    def set_pref(self, key: str, value: Any) -> None:
        self._prefs[key] = value
        self.save_prefs()

    def get_secret(self, key: str) -> Optional[str]:
        try:
            return keyring.get_password(APP_NAME, key)
        except keyring.errors.KeyringError:
            # No usable OS keyring backend (e.g. headless Linux); treat as unset.
            return None

    def set_secret(self, key: str, value: str) -> None:
        if value:
            keyring.set_password(APP_NAME, key, value)
            return
        try:
            keyring.delete_password(APP_NAME, key)
        except keyring.errors.PasswordDeleteError:
            pass
