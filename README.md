# MergeLY

Desktop AI Code Reviewer Assistant. MergeLY reviews GitLab Merge Requests or GitHub Pull Requests
against a Jira issue's acceptance criteria (or a manually-entered user story), using OpenAI to judge
feature completion, code quality, and security risk — then lets you post the result back to the VCS
and/or notify Google Chat, Slack, or Teams.

## Features

- **Multi-provider VCS support** — paste a GitLab MR or GitHub PR link; the provider is auto-detected
  (or pick one explicitly).
- **Requirement-aware review** — pulls acceptance criteria from a linked Jira issue (key detected in the
  title/branch/description), or falls back to a manual "User Story" text box.
- **AI-generated Markdown report** — `gpt-4o` returns structured JSON (verdict, feature verification
  matrix, code quality findings, security findings) rendered as a Markdown report in the app.
- **Actionable output** — post the review as a comment on the MR/PR, send a Google Chat/Slack/Teams
  webhook card, and/or save the report to a local SQLite history.
- **Responsive UI** — every network call (VCS, Jira, OpenAI, webhooks) runs on a `QThread` worker so the
  Qt UI thread never blocks.
- **Secure credential storage** — API tokens/keys live in the OS keyring (macOS Keychain, Windows
  Credential Locker, or a Linux Secret Service provider), never in plaintext config files.

## Project layout

```
MergeLY/
├── app.py                  # QApplication bootstrap: dark theme, SQLite init, launches MainWindow
├── requirements.txt
├── core/
│   ├── config.py            # Settings: keyring for secrets, JSON file for preferences
│   ├── db.py                 # SQLite history of past reviews
│   ├── vcs_client.py         # GitLab (python-gitlab) + GitHub (PyGithub) wrapper
│   ├── jira_client.py         # Jira issue lookup (atlassian-python-api)
│   ├── ai_engine.py           # OpenAI review call + Markdown rendering
│   └── notifier.py            # Google Chat / Slack / Teams webhook payloads
└── ui/
    ├── main_window.py         # QMainWindow hosting the three tabs
    ├── reviewer_tab.py         # Provider selector, URL/user-story input, report viewer, output actions
    ├── history_tab.py          # QTableWidget browser over the local SQLite history
    ├── settings_tab.py         # Credential + preference form
    ├── workers.py               # QThread workers (fetch, analyze, post comment, notify)
    └── theme.py                  # Dark Qt stylesheet
```

## Prerequisites

- Python 3.10+
- A GitLab and/or GitHub personal access token (repo/API scope) for the projects you want to review
- An OpenAI API key with access to `gpt-4o`
- Optional: a Jira API token (id.atlassian.com) and a Google Chat / Slack / Teams incoming webhook URL

## Setup

1. **Create and activate a virtual environment**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate        # macOS/Linux
   .venv\Scripts\activate           # Windows
   ```

2. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

3. **Run the app**

   ```bash
   python app.py
   ```

4. **Configure credentials** — open the **Settings** tab and fill in:
   - GitLab URL (your instance, defaults to `https://gitlab.com`) + GitLab token
   - GitHub token
   - Jira URL / email / API token (optional)
   - OpenAI API key (and model, defaults to `gpt-4o`)
   - Notification webhook URL + type (`google_chat` / `slack` / `teams`)
   - Default VCS provider

   Click **Save Credentials** — tokens/keys/webhook URL go straight to the OS keyring; the rest is
   saved to `~/.mergely/config.json`.

## Usage

1. On the **Reviewer** tab, paste a GitLab MR or GitHub PR URL (or pick a provider explicitly instead of
   auto-detect).
2. Optionally paste a user story / acceptance criteria — skipped automatically if a Jira issue key is
   found and Jira is configured.
3. Click **Analyze Code** and watch the status/progress bar while MergeLY fetches the diff and runs the
   AI review.
4. Read the generated report (verdict, feature verification matrix, code quality, security findings),
   then optionally **Post Comment to VCS**, **Send Google Chat Card**, and/or **Save to Local History**.
5. Browse past reviews on the **History** tab; select a row and click **Load Selected Report** to view it
   again.

## Local data storage

- `~/.mergely/config.json` — non-secret preferences (URLs, default provider, notifier type)
- `~/.mergely/mergely.db` — SQLite history of saved reviews
- OS keyring, service name `MergeLY` — GitLab/GitHub/Jira/OpenAI tokens and the webhook URL

## Notes on the OS keyring backend

- **macOS** — uses Keychain out of the box.
- **Windows** — uses Credential Locker out of the box.
- **Linux** — requires a Secret Service provider (e.g. `gnome-keyring` or `ksecretservice`). If none is
  available, install one, or fall back to a less secure backend with `pip install keyrings.alt` (stores
  obfuscated, not encrypted, secrets).
