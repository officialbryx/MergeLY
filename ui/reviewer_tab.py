"""Reviewer tab: paste an MR/PR URL, run the AI review, then act on the results."""
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSplitter,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from core.ai_engine import AIEngine, ReviewResult
from core.config import ConfigManager
from core.db import Database
from core.jira_client import JiraClient
from core.notifier import Notifier
from core.vcs_client import PROVIDER_GITHUB, PROVIDER_GITLAB, VCSClient, detect_provider
from ui.workers import AnalyzeWorker, FetchReviewWorker, NotifyWorker, PostCommentWorker


class ReviewerTab(QWidget):
    review_saved = Signal()

    def __init__(self, config: ConfigManager, db: Database, parent=None):
        super().__init__(parent)
        self.config = config
        self.db = db

        self._review_request = None
        self._jira_issue = None
        self._review_result: Optional[ReviewResult] = None
        self._review_id: Optional[int] = None
        self._notified = False
        self._last_markdown = ""

        self._fetch_worker = None
        self._analyze_worker = None
        self._comment_worker = None
        self._notify_worker = None

        self._build_ui()
        self._connect_signals()
        self._apply_default_provider()

    # ---------- UI construction ----------
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        layout.addWidget(self._build_provider_box())
        layout.addWidget(self._build_input_box())

        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.addWidget(self._build_user_story_box())
        splitter.addWidget(self._build_report_box())
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([150, 500])
        layout.addWidget(splitter, stretch=1)

        layout.addLayout(self._build_action_bar())
        layout.addLayout(self._build_output_actions())

    def _build_provider_box(self) -> QGroupBox:
        box = QGroupBox("VCS Provider")
        row = QHBoxLayout(box)

        self.radio_auto = QRadioButton("Auto-detect")
        self.radio_gitlab = QRadioButton("GitLab Merge Request")
        self.radio_github = QRadioButton("GitHub Pull Request")
        self.radio_auto.setChecked(True)

        self.provider_group = QButtonGroup(self)
        for btn in (self.radio_auto, self.radio_gitlab, self.radio_github):
            self.provider_group.addButton(btn)
            row.addWidget(btn)

        row.addStretch(1)
        self.detected_label = QLabel("")
        self.detected_label.setStyleSheet("color: #6fbf73; font-style: italic;")
        row.addWidget(self.detected_label)
        return box

    def _build_input_box(self) -> QGroupBox:
        box = QGroupBox("Merge / Pull Request")
        layout = QVBoxLayout(box)
        self.url_input = QLineEdit()
        self.url_input.setPlaceholderText(
            "Paste a GitLab MR URL (…/-/merge_requests/123) or GitHub PR URL (…/pull/123)"
        )
        layout.addWidget(self.url_input)
        return box

    def _build_user_story_box(self) -> QGroupBox:
        box = QGroupBox("User Story / Acceptance Criteria (used if Jira is disabled or unavailable)")
        layout = QVBoxLayout(box)
        self.user_story_edit = QTextEdit()
        self.user_story_edit.setPlaceholderText(
            "Optional: paste the user story / acceptance criteria here.\n"
            "If a Jira issue key is found in the title/branch and Jira is configured, it will be used instead."
        )
        layout.addWidget(self.user_story_edit)
        return box

    def _build_report_box(self) -> QGroupBox:
        box = QGroupBox("Review Report")
        layout = QVBoxLayout(box)
        self.report_viewer = QTextBrowser()
        self.report_viewer.setOpenExternalLinks(True)
        self.report_viewer.setPlaceholderText("The generated review report will appear here…")
        layout.addWidget(self.report_viewer)
        return box

    def _build_action_bar(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self.analyze_button = QPushButton("Analyze Code")
        self.analyze_button.setMinimumWidth(140)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.status_label = QLabel("Ready")

        row.addWidget(self.analyze_button)
        row.addWidget(self.progress_bar, stretch=1)
        row.addWidget(self.status_label)
        return row

    def _build_output_actions(self) -> QHBoxLayout:
        row = QHBoxLayout()
        self.notify_checkbox = QCheckBox("Send Notification automatically")
        self.post_comment_button = QPushButton("Post Comment to VCS")
        self.send_chat_button = QPushButton("Send Google Chat Card")
        self.save_history_button = QPushButton("Save to Local History")

        for btn in (self.post_comment_button, self.send_chat_button, self.save_history_button):
            btn.setEnabled(False)

        row.addWidget(self.notify_checkbox)
        row.addStretch(1)
        row.addWidget(self.post_comment_button)
        row.addWidget(self.send_chat_button)
        row.addWidget(self.save_history_button)
        return row

    # ---------- wiring ----------
    def _connect_signals(self) -> None:
        self.url_input.textChanged.connect(self._on_url_changed)
        self.analyze_button.clicked.connect(self._on_analyze_clicked)
        self.post_comment_button.clicked.connect(self._on_post_comment_clicked)
        self.send_chat_button.clicked.connect(self._on_send_notification_clicked)
        self.save_history_button.clicked.connect(self._on_save_history_clicked)

    def _apply_default_provider(self) -> None:
        radios = {"auto": self.radio_auto, "gitlab": self.radio_gitlab, "github": self.radio_github}
        default_provider = self.config.get_pref("default_provider", "auto")
        radios.get(default_provider, self.radio_auto).setChecked(True)

    def reload_clients(self) -> None:
        """Called after Settings are saved. Clients are rebuilt on demand, so there is nothing to cache."""

    def shutdown(self) -> None:
        for worker in (self._fetch_worker, self._analyze_worker, self._comment_worker, self._notify_worker):
            if worker is not None and worker.isRunning():
                worker.quit()
                worker.wait(3000)

    # ---------- helpers ----------
    def _selected_provider(self) -> Optional[str]:
        if self.radio_gitlab.isChecked():
            return PROVIDER_GITLAB
        if self.radio_github.isChecked():
            return PROVIDER_GITHUB
        return None  # auto-detect

    def _on_url_changed(self, text: str) -> None:
        if not self.radio_auto.isChecked():
            self.detected_label.setText("")
            return
        provider = detect_provider(text.strip()) if text.strip() else None
        if provider == PROVIDER_GITLAB:
            self.detected_label.setText("Detected: GitLab Merge Request")
        elif provider == PROVIDER_GITHUB:
            self.detected_label.setText("Detected: GitHub Pull Request")
        else:
            self.detected_label.setText("")

    def _set_busy(self, busy: bool, message: str = "") -> None:
        self.analyze_button.setEnabled(not busy)
        self.progress_bar.setRange(0, 0 if busy else 100)
        if not busy:
            self.progress_bar.setValue(0)
        if message:
            self.status_label.setText(message)

    def _make_vcs_client(self) -> VCSClient:
        return VCSClient(
            gitlab_url=self.config.get_pref("gitlab_url", "https://gitlab.com"),
            gitlab_token=self.config.get_secret("gitlab_token") or "",
            github_token=self.config.get_secret("github_token") or "",
        )

    def _make_jira_client(self) -> JiraClient:
        return JiraClient(
            url=self.config.get_pref("jira_url", ""),
            email=self.config.get_pref("jira_email", ""),
            token=self.config.get_secret("jira_token") or "",
        )

    def _make_ai_engine(self) -> AIEngine:
        return AIEngine(
            api_key=self.config.get_secret("openai_api_key") or "",
            model=self.config.get_pref("openai_model", "gpt-4o"),
        )

    def _make_notifier(self) -> Notifier:
        return Notifier(
            webhook_url=self.config.get_secret("chat_webhook_url") or "",
            kind=self.config.get_pref("notifier_type", "google_chat"),
        )

    # ---------- actions: analyze ----------
    def _on_analyze_clicked(self) -> None:
        url = self.url_input.text().strip()
        if not url:
            QMessageBox.warning(self, "Missing URL", "Please paste a GitLab MR or GitHub PR URL first.")
            return

        try:
            vcs_client = self._make_vcs_client()
        except Exception as exc:
            QMessageBox.critical(self, "Configuration Error", str(exc))
            return

        self._review_request = None
        self._jira_issue = None
        self._review_result = None
        self._review_id = None
        self._notified = False
        self.report_viewer.clear()
        for btn in (self.post_comment_button, self.send_chat_button, self.save_history_button):
            btn.setEnabled(False)

        self._set_busy(True, "Fetching merge/pull request…")

        use_jira = bool(self.config.get_pref("jira_url") and self.config.get_secret("jira_token"))
        self._fetch_worker = FetchReviewWorker(
            vcs_client=vcs_client,
            jira_client_factory=self._make_jira_client,
            url=url,
            provider=self._selected_provider(),
            use_jira=use_jira,
        )
        self._fetch_worker.progress.connect(self._on_worker_progress)
        self._fetch_worker.succeeded.connect(self._on_fetch_succeeded)
        self._fetch_worker.failed.connect(self._on_fetch_failed)
        self._fetch_worker.start()

    def _on_worker_progress(self, message: str) -> None:
        self.status_label.setText(message)

    def _on_fetch_failed(self, message: str) -> None:
        self._set_busy(False, "Ready")
        QMessageBox.critical(self, "Fetch Failed", message)

    def _on_fetch_succeeded(self, result: dict) -> None:
        self._review_request = result["review_request"]
        self._jira_issue = result["jira_issue"]

        if self._jira_issue is not None:
            requirement_text = (
                f"{self._jira_issue.summary}\n\n"
                f"{self._jira_issue.description}\n\n"
                f"Acceptance Criteria:\n{self._jira_issue.acceptance_criteria}"
            )
        else:
            requirement_text = self.user_story_edit.toPlainText().strip()

        try:
            ai_engine = self._make_ai_engine()
        except Exception as exc:
            self._set_busy(False, "Ready")
            QMessageBox.critical(self, "Configuration Error", str(exc))
            return

        self._set_busy(True, "Analyzing diff with OpenAI…")
        self._analyze_worker = AnalyzeWorker(
            ai_engine=ai_engine,
            diff_text=self._review_request.diff_text,
            requirement_text=requirement_text,
            pr_title=self._review_request.title,
            pr_description=self._review_request.description,
        )
        self._analyze_worker.progress.connect(self._on_worker_progress)
        self._analyze_worker.succeeded.connect(self._on_analyze_succeeded)
        self._analyze_worker.failed.connect(self._on_analyze_failed)
        self._analyze_worker.start()

    def _on_analyze_failed(self, message: str) -> None:
        self._set_busy(False, "Ready")
        QMessageBox.critical(self, "Analysis Failed", message)

    def _on_analyze_succeeded(self, result: ReviewResult) -> None:
        self._review_result = result
        self._set_busy(False, "Review complete")
        self._last_markdown = result.to_markdown(
            title=self._review_request.title if self._review_request else "",
            url=self._review_request.web_url if self._review_request else "",
        )
        self.report_viewer.setMarkdown(self._last_markdown)

        for btn in (self.post_comment_button, self.send_chat_button, self.save_history_button):
            btn.setEnabled(True)

        if self.notify_checkbox.isChecked():
            self._on_send_notification_clicked()

    # ---------- actions: post comment ----------
    def _on_post_comment_clicked(self) -> None:
        if not (self._review_request and self._review_result):
            return
        try:
            vcs_client = self._make_vcs_client()
        except Exception as exc:
            QMessageBox.critical(self, "Configuration Error", str(exc))
            return

        body = f"### 🤖 MergeLY Automated Code Review\n\n{self._last_markdown}"
        self.post_comment_button.setEnabled(False)
        self.status_label.setText("Posting comment to VCS…")
        self._comment_worker = PostCommentWorker(vcs_client, self._review_request, body)
        self._comment_worker.progress.connect(self._on_worker_progress)
        self._comment_worker.succeeded.connect(lambda *_: self._on_comment_posted())
        self._comment_worker.failed.connect(self._on_comment_failed)
        self._comment_worker.start()

    def _on_comment_posted(self) -> None:
        self.post_comment_button.setEnabled(True)
        self.status_label.setText("Comment posted")
        QMessageBox.information(self, "Success", "Review comment posted to the VCS.")

    def _on_comment_failed(self, message: str) -> None:
        self.post_comment_button.setEnabled(True)
        self.status_label.setText("Ready")
        QMessageBox.critical(self, "Post Comment Failed", message)

    # ---------- actions: notify ----------
    def _on_send_notification_clicked(self) -> None:
        if not self._review_result:
            return
        try:
            notifier = self._make_notifier()
        except Exception as exc:
            QMessageBox.critical(self, "Configuration Error", str(exc))
            return

        self.send_chat_button.setEnabled(False)
        self.status_label.setText("Sending notification…")
        self._notify_worker = NotifyWorker(
            notifier=notifier,
            title=self._review_request.title if self._review_request else "",
            verdict=self._review_result.verdict,
            summary=self._review_result.summary,
            url=self._review_request.web_url if self._review_request else "",
        )
        self._notify_worker.progress.connect(self._on_worker_progress)
        self._notify_worker.succeeded.connect(lambda *_: self._on_notification_sent())
        self._notify_worker.failed.connect(self._on_notification_failed)
        self._notify_worker.start()

    def _on_notification_sent(self) -> None:
        self.send_chat_button.setEnabled(True)
        self.status_label.setText("Notification sent")
        self._notified = True
        if self._review_id is not None:
            self.db.set_notified(self._review_id)

    def _on_notification_failed(self, message: str) -> None:
        self.send_chat_button.setEnabled(True)
        self.status_label.setText("Ready")
        QMessageBox.critical(self, "Notification Failed", message)

    # ---------- actions: save history ----------
    def _on_save_history_clicked(self) -> None:
        if not (self._review_request and self._review_result):
            return
        self._review_id = self.db.add_review(
            provider=self._review_request.provider,
            title=self._review_request.title,
            url=self._review_request.web_url,
            verdict=self._review_result.verdict,
            user_story=self.user_story_edit.toPlainText().strip(),
            report_markdown=self._last_markdown,
            raw_json=self._review_result.raw_json,
            notified=self._notified,
        )
        self.save_history_button.setEnabled(False)
        self.status_label.setText("Saved to local history")
        self.review_saved.emit()
