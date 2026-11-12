"""Check issue/PR metadata using trusted base code; never execute PR files.

Run in submissions.yml with GITHUB_EVENT_PATH, GITHUB_REPOSITORY and GITHUB_TOKEN.
PRs receive a head-commit status and one best-effort reminder; issues receive a label.
"""

import json
import os
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request

from release_notes import blocks

TITLE_LIMIT = 64
WORD_LIMIT = 200
CHAR_LIMIT = 6000
LABEL = "needs-description"
STATUS = "Submission format"
GUIDE = "https://github.com/den-run-ai/pystachy/blob/main/CONTRIBUTING.md#issues-and-pull-requests"
PR_ACTIONS = ("opened", "edited", "synchronize", "reopened", "ready_for_review")
# Tool attribution belongs in a sentence of the description, not in footers or session links.
FOOTER = re.compile(r"Generated (?:by|with) \[?(?:Claude|Codex|ChatGPT|Copilot)|^Co-Authored-By:|"
                    r"claude\.ai/code/session_|chatgpt\.com/codex/tasks/", re.I | re.M)
ACK_MARKER = "<!-- pystachy-ack-v1 -->"
ACK_BODY = (ACK_MARKER + "\nThanks for contributing! Please reply once to acknowledge "
            "the [contributor guidelines](https://github.com/den-run-ai/pystachy/blob/main/CONTRIBUTING.md), "
            "your right to submit this work under its applicable licenses, "
            "and any substantial AI assistance (tool and scope, or `AI: none`). "
            "You are responsible for reviewing and understanding your contribution. "
            "This reminder is **not a blocking check**.")


def wrapped(text):
    """Return whether a paragraph or list item continues on another line."""
    return any(kind == "text" and len(lines) > 1 for kind, lines in blocks(text))


def validate(title, body, is_pr=False):
    """Return actionable errors; count code, tables and collapsed details too."""
    errors = []
    if not title.strip() or len(title) > TITLE_LIMIT or "\n" in title or "\r" in title:
        errors.append("Use a nonempty, single-line title of at most 64 characters.")
    text = re.sub(r"<!--.*?-->", "", body or "", flags=re.S)
    if len(text.split()) > WORD_LIMIT or len(body or "") > CHAR_LIMIT:
        errors.append("Keep the whole body to 200 words and 6000 characters; link larger evidence.")
    expected = ["problem", "change", "validation"] if is_pr else ["problem", "scope", "done when"]
    sections = []
    fence = None
    for line in text.splitlines():
        marker = re.match(r"^\s{0,3}(`{3,}|~{3,})", line)
        if marker:
            run = marker[1]
            if fence is None:
                fence = run
            elif (run[0] == fence[0] and len(run) >= len(fence)
                  and not line[marker.end():].strip()):
                fence = None
            continue
        heading = re.fullmatch(r"##\s+(.+?)\s*", line) if fence is None else None
        if heading:
            sections.append([heading[1].lower(), ""])
        elif sections:
            sections[-1][1] += line + "\n"
    if [name for name, _ in sections] != expected:
        errors.append("Use these sections in order: " + ", ".join("## " + name.title() for name in expected) + ".")
    elif any(not re.search(r"\w", value) or value.strip().lower() == "_no response_"
             for _, value in sections):
        errors.append("Fill each section with a short, concrete answer.")
    if wrapped(text):
        errors.append("Write each paragraph and list item on one line; GitHub shows every newline "
                      "in a body as a line break.")
    if FOOTER.search(text):
        errors.append("Remove generated-by footers, Co-Authored-By lines and session links; "
                      "disclose AI assistance in a sentence instead.")
    return errors


def api(method, path, payload=None, missing_ok=False):
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(
        "https://api.github.com/repos/" + os.environ["GITHUB_REPOSITORY"] + path,
        data=data, method=method,
        headers={"Authorization": "Bearer " + os.environ["GITHUB_TOKEN"],
                 "Accept": "application/vnd.github+json", "Content-Type": "application/json",
                 "X-GitHub-Api-Version": "2022-11-28"})
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            content = response.read()
            return json.loads(content) if content else None
    except urllib.error.HTTPError as error:
        if missing_ok and error.code == 404:
            return None
        raise


def remind_contributor(number):
    """Deduplicate our bot's reminder across all pages; never fail metadata checks."""
    try:
        page = 1
        while True:
            comments = api("GET", f"/issues/{number}/comments?per_page=100&page={page}")
            if any(comment.get("user", {}).get("login") == "github-actions[bot]"
                   and comment.get("user", {}).get("type") == "Bot"
                   and ACK_MARKER in (comment.get("body") or "") for comment in comments):
                return
            if len(comments) < 100:
                break
            page += 1
        api("POST", f"/issues/{number}/comments", {"body": ACK_BODY})
    except (OSError, ValueError):
        # HTTP/connection/time-out/JSON failures must not turn this into a gate.
        # A later PR metadata event retries, including after a cancelled opening run.
        print("Contributor reminder unavailable; metadata validation is unchanged.", file=sys.stderr)


def check(event):
    is_pr = "pull_request" in event
    number = event["pull_request" if is_pr else "issue"]["number"]
    # Delayed events must not restore stale labels/statuses after an author edits.
    current = api("GET", f"/pulls/{number}" if is_pr else f"/issues/{number}")
    if current["state"] != "open":
        return []
    errors = validate(current["title"], current.get("body"), is_pr)
    if is_pr:
        api("POST", "/statuses/" + current["head"]["sha"], {
            "state": "failure" if errors else "success", "context": STATUS,
            "description": "Shorten or complete title/body; see CONTRIBUTING.md." if errors
                           else "Title and three-section body meet the reading budget.",
            "target_url": GUIDE})
        if event.get("action") in PR_ACTIONS:
            remind_contributor(number)
    elif errors:
        if api("GET", "/labels/" + LABEL, missing_ok=True) is None:
            try:
                api("POST", "/labels", {"name": LABEL, "color": "fbca04",
                    "description": "Use a <=64-character title and three filled sections, <=200 words; see CONTRIBUTING.md."})
            except urllib.error.HTTPError as error:
                # Another issue's concurrent run may have created the label.
                if error.code != 422 or api("GET", "/labels/" + LABEL, missing_ok=True) is None:
                    raise
        api("POST", f"/issues/{number}/labels", {"labels": [LABEL]})
    else:
        api("DELETE", f"/issues/{number}/labels/{LABEL}", missing_ok=True)
    return errors


def main():
    event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text())
    errors = check(event)
    report = "\n".join(["## Submission format", *errors, "", "[Writing guide](" + GUIDE + ")"])
    print(report)
    if "GITHUB_STEP_SUMMARY" in os.environ:
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
            summary.write(report + "\n")
    return int(bool(errors))


if __name__ == "__main__":
    sys.exit(main())
