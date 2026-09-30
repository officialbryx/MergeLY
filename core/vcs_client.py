"""Unified GitLab / GitHub client: URL parsing, diff fetching, and comment posting."""
import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from urllib.parse import urlparse

import gitlab
from github import Auth, Github

PROVIDER_GITLAB = "gitlab"
PROVIDER_GITHUB = "github"


class VCSError(Exception):
    pass


@dataclass
class DiffFile:
    path: str
    status: str
    diff: str


@dataclass
class ReviewRequest:
    provider: str
    web_url: str
    project_ref: str  # "group/project" (GitLab) or "owner/repo" (GitHub)
    request_id: str  # MR iid / PR number, as a string
    title: str
    description: str
    author: str
    source_branch: str
    target_branch: str
    files: List[DiffFile] = field(default_factory=list)

    @property
    def diff_text(self) -> str:
        parts = [f"--- {f.path} ({f.status}) ---\n{f.diff}" for f in self.files]
        return "\n\n".join(parts)


def detect_provider(url: str) -> Optional[str]:
    """Guess the VCS provider from a pasted MR/PR URL."""
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    path = parsed.path.lower()
    if "github.com" in host and "/pull/" in path:
        return PROVIDER_GITHUB
    if "/-/merge_requests/" in path:
        return PROVIDER_GITLAB
    return None


class VCSClient:
    def __init__(self, gitlab_url: str = "https://gitlab.com", gitlab_token: str = "", github_token: str = ""):
        self.gitlab_url = gitlab_url or "https://gitlab.com"
        self.gitlab_token = gitlab_token
        self.github_token = github_token

    # ---------- GitLab ----------
    def _gitlab(self) -> "gitlab.Gitlab":
        return gitlab.Gitlab(self.gitlab_url, private_token=self.gitlab_token or None)

    @staticmethod
    def parse_gitlab_url(url: str) -> Tuple[str, str]:
        path = urlparse(url).path
        match = re.search(r"^/(.+)/-/merge_requests/(\d+)", path)
        if not match:
            raise VCSError("Could not parse GitLab MR URL")
        project_path, mr_iid = match.groups()
        return project_path, mr_iid

    def fetch_gitlab_mr(self, url: str) -> ReviewRequest:
        project_path, mr_iid = self.parse_gitlab_url(url)
        gl = self._gitlab()
        try:
            project = gl.projects.get(project_path)
            mr = project.mergerequests.get(int(mr_iid))
            changes = mr.changes()
        except Exception as exc:
            raise VCSError(f"Failed to fetch GitLab MR: {exc}") from exc

        files = []
        for change in changes.get("changes", []):
            status = "modified"
            if change.get("new_file"):
                status = "added"
            elif change.get("deleted_file"):
                status = "deleted"
            elif change.get("renamed_file"):
                status = "renamed"
            files.append(
                DiffFile(
                    path=change.get("new_path") or change.get("old_path") or "",
                    status=status,
                    diff=change.get("diff", ""),
                )
            )

        return ReviewRequest(
            provider=PROVIDER_GITLAB,
            web_url=mr.web_url,
            project_ref=project_path,
            request_id=str(mr_iid),
            title=mr.title,
            description=mr.description or "",
            author=(mr.author or {}).get("username", "unknown"),
            source_branch=mr.source_branch,
            target_branch=mr.target_branch,
            files=files,
        )

    def post_gitlab_comment(self, project_ref: str, request_id: str, body: str) -> None:
        gl = self._gitlab()
        try:
            project = gl.projects.get(project_ref)
            mr = project.mergerequests.get(int(request_id))
            mr.notes.create({"body": body})
        except Exception as exc:
            raise VCSError(f"Failed to post GitLab comment: {exc}") from exc

    # ---------- GitHub ----------
    def _github(self) -> Github:
        if self.github_token:
            return Github(auth=Auth.Token(self.github_token))
        return Github()

    @staticmethod
    def parse_github_url(url: str) -> Tuple[str, str]:
        path = urlparse(url).path
        match = re.search(r"^/([^/]+/[^/]+)/pull/(\d+)", path)
        if not match:
            raise VCSError("Could not parse GitHub PR URL")
        repo_full_name, pr_number = match.groups()
        return repo_full_name, pr_number

    def fetch_github_pr(self, url: str) -> ReviewRequest:
        repo_full_name, pr_number = self.parse_github_url(url)
        gh = self._github()
        try:
            repo = gh.get_repo(repo_full_name)
            pr = repo.get_pull(int(pr_number))
            files = [
                DiffFile(path=f.filename, status=f.status, diff=f.patch or "")
                for f in pr.get_files()
            ]
        except Exception as exc:
            raise VCSError(f"Failed to fetch GitHub PR: {exc}") from exc

        return ReviewRequest(
            provider=PROVIDER_GITHUB,
            web_url=pr.html_url,
            project_ref=repo_full_name,
            request_id=str(pr_number),
            title=pr.title,
            description=pr.body or "",
            author=pr.user.login if pr.user else "unknown",
            source_branch=pr.head.ref,
            target_branch=pr.base.ref,
            files=files,
        )

    def post_github_comment(self, project_ref: str, request_id: str, body: str) -> None:
        gh = self._github()
        try:
            repo = gh.get_repo(project_ref)
            pr = repo.get_pull(int(request_id))
            pr.create_issue_comment(body)
        except Exception as exc:
            raise VCSError(f"Failed to post GitHub comment: {exc}") from exc

    # ---------- Unified ----------
    def fetch(self, url: str, provider: Optional[str] = None) -> ReviewRequest:
        provider = provider or detect_provider(url)
        if provider == PROVIDER_GITLAB:
            return self.fetch_gitlab_mr(url)
        if provider == PROVIDER_GITHUB:
            return self.fetch_github_pr(url)
        raise VCSError("Unable to detect VCS provider from URL; select one explicitly.")

    def post_comment(self, review: ReviewRequest, body: str) -> None:
        if review.provider == PROVIDER_GITLAB:
            self.post_gitlab_comment(review.project_ref, review.request_id, body)
        elif review.provider == PROVIDER_GITHUB:
            self.post_github_comment(review.project_ref, review.request_id, body)
        else:
            raise VCSError(f"Unknown provider: {review.provider}")
