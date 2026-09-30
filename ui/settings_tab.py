"""Settings tab: credentials go straight to the OS keyring; everything else is a local preference."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.config import ConfigManager


class SettingsTab(QWidget):
    credentials_saved = Signal()

    def __init__(self, config: ConfigManager, parent=None):
        super().__init__(parent)
        self.config = config
        self._build_ui()
        self._load_values()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        vcs_box = QGroupBox("Version Control")
        vcs_form = QFormLayout(vcs_box)
        self.gitlab_url_edit = QLineEdit()
        self.gitlab_token_edit = QLineEdit()
        self.gitlab_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.github_token_edit = QLineEdit()
        self.github_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        vcs_form.addRow("GitLab URL:", self.gitlab_url_edit)
        vcs_form.addRow("GitLab Token:", self.gitlab_token_edit)
        vcs_form.addRow("GitHub Token:", self.github_token_edit)

        jira_box = QGroupBox("Jira")
        jira_form = QFormLayout(jira_box)
        self.jira_url_edit = QLineEdit()
        self.jira_email_edit = QLineEdit()
        self.jira_token_edit = QLineEdit()
        self.jira_token_edit.setEchoMode(QLineEdit.EchoMode.Password)
        jira_form.addRow("Jira URL:", self.jira_url_edit)
        jira_form.addRow("Jira Email:", self.jira_email_edit)
        jira_form.addRow("Jira API Token:", self.jira_token_edit)

        ai_box = QGroupBox("OpenAI")
        ai_form = QFormLayout(ai_box)
        self.openai_key_edit = QLineEdit()
        self.openai_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.openai_model_edit = QLineEdit()
        ai_form.addRow("OpenAI API Key:", self.openai_key_edit)
        ai_form.addRow("Model:", self.openai_model_edit)

        notify_box = QGroupBox("Notifications")
        notify_form = QFormLayout(notify_box)
        self.webhook_url_edit = QLineEdit()
        self.webhook_url_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.notifier_kind_combo = QComboBox()
        self.notifier_kind_combo.addItems(["google_chat", "slack", "teams"])
        notify_form.addRow("Webhook URL:", self.webhook_url_edit)
        notify_form.addRow("Webhook Type:", self.notifier_kind_combo)

        general_box = QGroupBox("General")
        general_form = QFormLayout(general_box)
        self.default_provider_combo = QComboBox()
        self.default_provider_combo.addItems(["auto", "gitlab", "github"])
        general_form.addRow("Default Provider:", self.default_provider_combo)

        self.save_button = QPushButton("Save Credentials")
        self.save_button.clicked.connect(self._on_save_clicked)
        self.status_label = QLabel("")

        for box in (vcs_box, jira_box, ai_box, notify_box, general_box):
            layout.addWidget(box)
        layout.addWidget(self.save_button)
        layout.addWidget(self.status_label)
        layout.addStretch(1)

    def _load_values(self) -> None:
        self.gitlab_url_edit.setText(self.config.get_pref("gitlab_url", "https://gitlab.com"))
        self.gitlab_token_edit.setText(self.config.get_secret("gitlab_token") or "")
        self.github_token_edit.setText(self.config.get_secret("github_token") or "")

        self.jira_url_edit.setText(self.config.get_pref("jira_url", ""))
        self.jira_email_edit.setText(self.config.get_pref("jira_email", ""))
        self.jira_token_edit.setText(self.config.get_secret("jira_token") or "")

        self.openai_key_edit.setText(self.config.get_secret("openai_api_key") or "")
        self.openai_model_edit.setText(self.config.get_pref("openai_model", "gpt-4o"))

        self.webhook_url_edit.setText(self.config.get_secret("chat_webhook_url") or "")
        self.notifier_kind_combo.setCurrentText(self.config.get_pref("notifier_type", "google_chat"))

        self.default_provider_combo.setCurrentText(self.config.get_pref("default_provider", "auto"))

    def _on_save_clicked(self) -> None:
        self.config.set_pref("gitlab_url", self.gitlab_url_edit.text().strip() or "https://gitlab.com")
        self.config.set_pref("jira_url", self.jira_url_edit.text().strip())
        self.config.set_pref("jira_email", self.jira_email_edit.text().strip())
        self.config.set_pref("openai_model", self.openai_model_edit.text().strip() or "gpt-4o")
        self.config.set_pref("notifier_type", self.notifier_kind_combo.currentText())
        self.config.set_pref("default_provider", self.default_provider_combo.currentText())

        try:
            self.config.set_secret("gitlab_token", self.gitlab_token_edit.text().strip())
            self.config.set_secret("github_token", self.github_token_edit.text().strip())
            self.config.set_secret("jira_token", self.jira_token_edit.text().strip())
            self.config.set_secret("openai_api_key", self.openai_key_edit.text().strip())
            self.config.set_secret("chat_webhook_url", self.webhook_url_edit.text().strip())
        except Exception as exc:
            QMessageBox.critical(self, "Keyring Error", f"Failed to save credentials securely: {exc}")
            return

        self.status_label.setText("Credentials saved securely.")
        self.credentials_saved.emit()
