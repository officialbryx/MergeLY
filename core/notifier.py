"""Dispatches review outcomes to Google Chat, Slack, or Teams incoming webhooks."""
import requests

KIND_GOOGLE_CHAT = "google_chat"
KIND_SLACK = "slack"
KIND_TEAMS = "teams"


class NotifierError(Exception):
    pass


class Notifier:
    def __init__(self, webhook_url: str, kind: str = KIND_GOOGLE_CHAT):
        self.webhook_url = webhook_url
        self.kind = kind

    def send(self, *, title: str, verdict: str, summary: str, url: str = "") -> None:
        if not self.webhook_url:
            raise NotifierError("Notification webhook URL is not configured")
        payload = self._build_payload(title=title, verdict=verdict, summary=summary, url=url)
        try:
            response = requests.post(self.webhook_url, json=payload, timeout=15)
            response.raise_for_status()
        except requests.RequestException as exc:
            raise NotifierError(f"Failed to send notification: {exc}") from exc

    def _build_payload(self, *, title: str, verdict: str, summary: str, url: str) -> dict:
        is_good = verdict.strip().upper() == "GOOD TO GO"
        icon = "✅" if is_good else "⚠️"
        header = f"{icon} Code Review: {verdict}"

        if self.kind == KIND_SLACK:
            return {"text": f"*{header}*\n*{title}*\n{summary}\n{url}"}

        if self.kind == KIND_TEAMS:
            return {
                "@type": "MessageCard",
                "@context": "http://schema.org/extensions",
                "summary": header,
                "themeColor": "2ECC71" if is_good else "E74C3C",
                "title": header,
                "sections": [{"activityTitle": title, "text": summary}],
                "potentialAction": (
                    [{"@type": "OpenUri", "name": "Open", "targets": [{"os": "default", "uri": url}]}]
                    if url
                    else []
                ),
            }

        # Default: Google Chat card
        widgets = [
            {"decoratedText": {"text": header}},
            {"textParagraph": {"text": summary}},
        ]
        if url:
            widgets.append({"buttonList": {"buttons": [{"text": "Open Review", "onClick": {"openLink": {"url": url}}}]}})
        return {
            "cardsV2": [
                {
                    "cardId": "mergely-review",
                    "card": {
                        "header": {"title": "MergeLY Code Review", "subtitle": title},
                        "sections": [{"widgets": widgets}],
                    },
                }
            ]
        }
