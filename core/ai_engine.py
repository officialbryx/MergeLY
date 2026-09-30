"""OpenAI-powered review engine: sends diff + requirements, returns structured JSON, renders Markdown."""
import json
from dataclasses import dataclass, field
from typing import List

from openai import OpenAI

SYSTEM_PROMPT = """You are MergeLY, a senior staff software engineer acting as an automated corporate code \
reviewer. You are given a merge/pull request's title, description, a requirement (user story or Jira \
acceptance criteria), and a unified code diff.

Evaluate three things:
1. Feature completion: does the diff satisfy each acceptance criterion / requirement? If none are given, \
infer 2-4 reasonable checks from the title and description.
2. Code quality: style, maintainability, complexity, error handling, missing tests.
3. Security risks: injection, broken auth, secrets in code, unsafe deserialization, missing input \
validation, and other OWASP Top 10-style issues.

Decide the overall "verdict": use "NEEDS WORK" if any acceptance criterion is NOT MET, or if any HIGH or \
CRITICAL severity code quality or security finding exists. Otherwise use "GOOD TO GO".
"""

RESPONSE_SCHEMA_HINT = """
Respond ONLY with a single JSON object of this exact shape (omit markdown fences):
{
  "verdict": "GOOD TO GO" | "NEEDS WORK",
  "summary": "<2-4 sentence overview>",
  "feature_verification": [
    {"criterion": "<requirement or acceptance criterion>", "status": "MET" | "PARTIAL" | "NOT MET", "notes": "<evidence from the diff>"}
  ],
  "code_quality": [
    {"file": "<path>", "severity": "LOW" | "MEDIUM" | "HIGH", "description": "<issue>", "suggestion": "<fix>"}
  ],
  "security_findings": [
    {"file": "<path>", "severity": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL", "description": "<vulnerability>", "suggestion": "<mitigation>"}
  ]
}
Use an empty list for any category with no findings.
"""


class AIEngineError(Exception):
    pass


@dataclass
class FeatureCheck:
    criterion: str
    status: str
    notes: str = ""


@dataclass
class QualityFinding:
    file: str
    severity: str
    description: str
    suggestion: str = ""


@dataclass
class ReviewResult:
    verdict: str
    summary: str
    feature_verification: List[FeatureCheck] = field(default_factory=list)
    code_quality: List[QualityFinding] = field(default_factory=list)
    security_findings: List[QualityFinding] = field(default_factory=list)
    raw_json: str = ""

    def to_markdown(self, title: str = "", url: str = "") -> str:
        def esc(text: str) -> str:
            return (text or "").replace("|", "\\|").replace("\n", "<br>")

        is_good = self.verdict.strip().upper() == "GOOD TO GO"
        lines = ["# Code Review Report", ""]
        if title:
            lines.append(f"**Subject:** {esc(title)}")
        if url:
            lines.append(f"**Link:** {url}")
        lines.append(f"**Verdict:** {'✅ GOOD TO GO' if is_good else '⚠️ NEEDS WORK'}")
        lines.append("")
        lines.append("## Summary")
        lines.append(self.summary or "_No summary provided._")
        lines.append("")
        lines.append("## Feature Verification Matrix")
        if self.feature_verification:
            lines.append("| Criterion | Status | Notes |")
            lines.append("|---|---|---|")
            for f in self.feature_verification:
                lines.append(f"| {esc(f.criterion)} | {esc(f.status)} | {esc(f.notes)} |")
        else:
            lines.append("_No acceptance criteria evaluated._")
        lines.append("")
        lines.append("## Code Quality")
        if self.code_quality:
            lines.append("| File | Severity | Description | Suggestion |")
            lines.append("|---|---|---|---|")
            for q in self.code_quality:
                lines.append(f"| {esc(q.file)} | {esc(q.severity)} | {esc(q.description)} | {esc(q.suggestion)} |")
        else:
            lines.append("_No code quality issues found._")
        lines.append("")
        lines.append("## Security Findings")
        if self.security_findings:
            lines.append("| File | Severity | Description | Suggestion |")
            lines.append("|---|---|---|---|")
            for s in self.security_findings:
                lines.append(f"| {esc(s.file)} | {esc(s.severity)} | {esc(s.description)} | {esc(s.suggestion)} |")
        else:
            lines.append("_No security issues found._")
        return "\n".join(lines)


class AIEngine:
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        if not api_key:
            raise AIEngineError("OpenAI API key is not configured")
        self._client = OpenAI(api_key=api_key)
        self.model = model

    def review(self, *, diff_text: str, requirement_text: str, pr_title: str, pr_description: str) -> ReviewResult:
        user_prompt = self._build_prompt(diff_text, requirement_text, pr_title, pr_description)
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT + RESPONSE_SCHEMA_HINT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
        except Exception as exc:
            raise AIEngineError(f"OpenAI request failed: {exc}") from exc

        content = response.choices[0].message.content or "{}"
        return self._parse_response(content)

    @staticmethod
    def _build_prompt(diff_text: str, requirement_text: str, pr_title: str, pr_description: str) -> str:
        max_chars = 120_000
        snippet = diff_text[:max_chars]
        if len(diff_text) > max_chars:
            snippet += "\n\n[... diff truncated for length ...]"
        return (
            f"## PR/MR Title\n{pr_title}\n\n"
            f"## PR/MR Description\n{pr_description or '_none_'}\n\n"
            f"## Requirement / User Story / Acceptance Criteria\n{requirement_text or '_none provided_'}\n\n"
            f"## Code Diff\n```diff\n{snippet}\n```\n"
        )

    @staticmethod
    def _parse_response(content: str) -> ReviewResult:
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise AIEngineError(f"Model returned invalid JSON: {exc}") from exc

        feature_verification = [
            FeatureCheck(
                criterion=item.get("criterion", ""),
                status=item.get("status", ""),
                notes=item.get("notes", ""),
            )
            for item in data.get("feature_verification", []) or []
        ]
        code_quality = [
            QualityFinding(
                file=item.get("file", ""),
                severity=item.get("severity", ""),
                description=item.get("description", ""),
                suggestion=item.get("suggestion", ""),
            )
            for item in data.get("code_quality", []) or []
        ]
        security_findings = [
            QualityFinding(
                file=item.get("file", ""),
                severity=item.get("severity", ""),
                description=item.get("description", ""),
                suggestion=item.get("suggestion", ""),
            )
            for item in data.get("security_findings", []) or []
        ]

        return ReviewResult(
            # Default to the fail-closed verdict if the model omits/garbles the field.
            verdict=data.get("verdict", "NEEDS WORK"),
            summary=data.get("summary", ""),
            feature_verification=feature_verification,
            code_quality=code_quality,
            security_findings=security_findings,
            raw_json=json.dumps(data, indent=2),
        )
