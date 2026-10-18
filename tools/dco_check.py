"""Check the DCO sign-offs of a fork pull request's commits (.github/workflows/dco.yml).

Every non-merge commit needs a "Signed-off-by: Name <email>" line naming its author or its
committer (CONTRIBUTING.md); commits of GitHub's bot accounts are left out, as the DCO app
left them. In the workflow this file is main's, and the pull request's commits come from the
REST API: nothing of the pull request runs here.
usage: dco_check.py              (GITHUB_EVENT_PATH, GITHUB_REPOSITORY and GITHUB_TOKEN set)
       dco_check.py COMMITS.json (the API's list of a pull request's commits, saved)
"""

import json
import os
import re
import sys
import urllib.request

SIGNOFF = re.compile(r"^Signed-off-by:[ \t]*(.+?)[ \t]*<([^<>\s]+)>[ \t\r]*$", re.IGNORECASE | re.MULTILINE)
PAGE = 100
# CONTRIBUTING.md's sign-off rule binds the pull requests opened after it was merged (#666)
POLICY = "2026-10-18T04:45:51Z"


def printable(text):
    """TEXT without control characters (a name in the log cannot start a workflow command)."""
    return "".join(c for c in text if c.isprintable())


def unsigned(commits):
    """One line for each commit of COMMITS (the API's objects) that lacks a valid sign-off."""
    bad = []
    for item in commits:
        if len(item["parents"]) > 1 or (item.get("author") or {}).get("type") == "Bot":
            continue
        commit = item["commit"]
        people = {(p["name"].strip().lower(), p["email"].strip().lower())
                  for p in (commit["author"], commit["committer"])}
        signoffs = {(name.lower(), email.lower()) for name, email in SIGNOFF.findall(commit["message"])}
        if signoffs & people:
            continue
        author = commit["author"]
        why = "no Signed-off-by line" if not signoffs else "no Signed-off-by line names its author or committer"
        bad.append(item["sha"][:12] + " (" + printable(author["name"]) + " <" + printable(author["email"])
                   + ">): " + why)
    return bad


def pull_commits(repo, number, token):
    """The commits of pull request NUMBER of REPO, a page of PAGE at a time."""
    commits = []
    page = 1
    while True:
        request = urllib.request.Request(
            f"https://api.github.com/repos/{repo}/pulls/{number}/commits?per_page={PAGE}&page={page}",
            headers={"Accept": "application/vnd.github+json", "Authorization": "Bearer " + token,
                     "X-GitHub-Api-Version": "2022-11-28"})
        with urllib.request.urlopen(request, timeout=60) as response:
            batch = json.load(response)
        commits += batch
        if len(batch) < PAGE:
            return commits
        page += 1


def main():
    if len(sys.argv) > 2:
        print("usage: dco_check.py [COMMITS.json]", file=sys.stderr)
        return 2
    if len(sys.argv) == 2:
        with open(sys.argv[1], encoding="utf-8") as f:
            commits = json.load(f)
    else:
        with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as f:
            pull = json.load(f)["pull_request"]
        if pull["created_at"] < POLICY:  # (UTC timestamps of one format compare as text)
            print(f"opened {pull['created_at']}, before the sign-off rule ({POLICY}): not checked")
            return 0
        commits = pull_commits(os.environ["GITHUB_REPOSITORY"], pull["number"], os.environ["GITHUB_TOKEN"])
        # (the API lists at most 250 commits of a pull request: a longer one is not checked whole)
        if len(commits) != pull["commits"]:
            print(f"dco_check.py: the API listed {len(commits)} of the pull request's {pull['commits']} commits",
                  file=sys.stderr)
            return 1
    bad = unsigned(commits)
    for line in bad:
        print(line)
    if bad:
        print(f"{len(bad)} of {len(commits)} commits lack a sign-off. After reading https://developercertificate.org/,"
              " add your own with git commit --amend -s (the last commit) or git rebase --signoff BASE (each"
              " commit since BASE), then push again; CONTRIBUTING.md has the rules.")
        return 1
    print(f"{len(commits)} commits signed off")
    return 0


if __name__ == "__main__":
    sys.exit(main())
