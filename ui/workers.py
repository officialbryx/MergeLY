"""QThread workers so VCS/Jira/OpenAI/webhook calls never block the Qt UI thread."""
from typing import Callable, Optional

from PySide6.QtCore import QThread, Signal

from core.ai_engine import AIEngine, ReviewResult
from core.jira_client import JiraClient
from core.notifier import Notifier
from core.vcs_client import ReviewRequest, VCSClient


class BaseWorker(QThread):
    succeeded = Signal(object)
    failed = Signal(str)
    progress = Signal(str)

    def run(self) -> None:
        try:
            result = self.execute()
        except Exception as exc:  # noqa: BLE001 - surface all worker errors to the UI
            self.failed.emit(str(exc))
            return
        self.succeeded.emit(result)

    def execute(self):
        raise NotImplementedError


class FetchReviewWorker(BaseWorker):
    """Fetches MR/PR metadata + diff, then best-effort enriches with a linked Jira issue."""

    def __init__(
        self,
        vcs_client: VCSClient,
        jira_client_factory: Callable[[], JiraClient],
        url: str,
        provider: Optional[str],
        use_jira: bool,
    ):
        super().__init__()
        self._vcs_client = vcs_client
        self._jira_client_factory = jira_client_factory
        self._url = url
        self._provider = provider
        self._use_jira = use_jira

    def execute(self) -> dict:
        self.progress.emit("Fetching merge/pull request details…")
        review_request = self._vcs_client.fetch(self._url, self._provider)

        jira_issue = None
        if self._use_jira:
            self.progress.emit("Looking up linked Jira issue…")
            try:
                jira_client = self._jira_client_factory()
                key = jira_client.extract_issue_key(
                    review_request.title, review_request.source_branch, review_request.description
                )
                if key:
                    jira_issue = jira_client.get_issue(key)
            except Exception:
                self.progress.emit("Jira lookup unavailable; falling back to manual user story.")

        return {"review_request": review_request, "jira_issue": jira_issue}


class AnalyzeWorker(BaseWorker):
    def __init__(self, ai_engine: AIEngine, diff_text: str, requirement_text: str, pr_title: str, pr_description: str):
        super().__init__()
        self._ai_engine = ai_engine
        self._diff_text = diff_text
        self._requirement_text = requirement_text
        self._pr_title = pr_title
        self._pr_description = pr_description

    def execute(self) -> ReviewResult:
        self.progress.emit("Sending diff to OpenAI for review…")
        return self._ai_engine.review(
            diff_text=self._diff_text,
            requirement_text=self._requirement_text,
            pr_title=self._pr_title,
            pr_description=self._pr_description,
        )


class PostCommentWorker(BaseWorker):
    def __init__(self, vcs_client: VCSClient, review_request: ReviewRequest, body: str):
        super().__init__()
        self._vcs_client = vcs_client
        self._review_request = review_request
        self._body = body

    def execute(self) -> bool:
        self.progress.emit("Posting comment to VCS…")
        self._vcs_client.post_comment(self._review_request, self._body)
        return True


class NotifyWorker(BaseWorker):
    def __init__(self, notifier: Notifier, title: str, verdict: str, summary: str, url: str):
        super().__init__()
        self._notifier = notifier
        self._title = title
        self._verdict = verdict
        self._summary = summary
        self._url = url

    def execute(self) -> bool:
        self.progress.emit("Sending notification…")
        self._notifier.send(title=self._title, verdict=self._verdict, summary=self._summary, url=self._url)
        return True
