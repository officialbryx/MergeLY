"""Jira integration: extract issue keys from titles/branches and pull acceptance criteria."""
import re
from dataclasses import dataclass
from typing import Any, Optional

from atlassian import Jira

ISSUE_KEY_PATTERN = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")

# Block-level ADF node types that should end with a line break when rendered as plain text.
_ADF_BLOCK_TYPES = {"paragraph", "heading", "listItem", "codeBlock"}


class JiraError(Exception):
    pass


@dataclass
class JiraIssue:
    key: str
    summary: str
    description: str
    acceptance_criteria: str
    issue_type: str
    status: str
    url: str


class JiraClient:
    def __init__(self, url: str, email: str, token: str):
        if not (url and email and token):
            raise JiraError("Jira is not configured")
        self.url = url.rstrip("/")
        self._jira = Jira(url=self.url, username=email, password=token, cloud=True)

    @staticmethod
    def extract_issue_key(*texts: Optional[str]) -> Optional[str]:
        for text in texts:
            if not text:
                continue
            match = ISSUE_KEY_PATTERN.search(text)
            if match:
                return match.group(1)
        return None

    def get_issue(self, key: str) -> JiraIssue:
        try:
            data = self._jira.issue(key)
        except Exception as exc:
            raise JiraError(f"Failed to fetch Jira issue {key}: {exc}") from exc

        fields = data.get("fields", {})
        description = self._render_description(fields.get("description"))
        acceptance_criteria = self._extract_acceptance_criteria(fields, description)

        return JiraIssue(
            key=data.get("key", key),
            summary=fields.get("summary", ""),
            description=description,
            acceptance_criteria=acceptance_criteria,
            issue_type=(fields.get("issuetype") or {}).get("name", ""),
            status=(fields.get("status") or {}).get("name", ""),
            url=f"{self.url}/browse/{data.get('key', key)}",
        )

    @staticmethod
    def _render_description(description: Any) -> str:
        if description is None:
            return ""
        if isinstance(description, str):
            return description
        return JiraClient._adf_to_text(description)  # Jira Cloud returns Atlassian Document Format

    @staticmethod
    def _adf_to_text(node: Any) -> str:
        if isinstance(node, str):
            return node
        if not isinstance(node, dict):
            return ""
        if node.get("type") == "text":
            return node.get("text", "")
        text = "".join(JiraClient._adf_to_text(child) for child in node.get("content", []) or [])
        return text + "\n" if node.get("type") in _ADF_BLOCK_TYPES else text

    @staticmethod
    def _extract_acceptance_criteria(fields: dict, description: str) -> str:
        for key, value in fields.items():
            if key.startswith("customfield_") and isinstance(value, str) and "acceptance" in key.lower():
                return value
        match = re.search(r"(Acceptance Criteria.*)", description, re.IGNORECASE | re.DOTALL)
        return match.group(1) if match else ""
