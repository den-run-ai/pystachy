"""Check that a fork pull request's author has certified the DCO (.github/workflows/dco.yml).

Contributors certify the Developer Certificate of Origin once, with a line for their GitHub
account in .github/dco-signers.txt (CONTRIBUTING.md). The check passes when main's copy of
that file lists the pull request's author, or the pull request's own copy does (a first pull
request adds the line). In the workflow this file and the signers file are main's, and the
pull request's copy comes from the REST API: nothing of the pull request runs here.
usage: dco_check.py   (with GITHUB_EVENT_PATH, GITHUB_REPOSITORY and GITHUB_TOKEN set)
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request

SIGNERS = ".github/dco-signers.txt"
# "@login Full Name <email>", which " for COMPANY" may follow
LINE = re.compile(r"^@([A-Za-z0-9-]+)[ \t]+[^<>\n]*[^<>\s][ \t]*<[^<>\s]+@[^<>\s]+>", re.MULTILINE)


def signers(text):
    """The GitHub logins, lowercased, that the lines of a signers file certify."""
    return {login.lower() for login in LINE.findall(text)}


def pull_copy(repo, sha, token):
    """The signers file of commit SHA of REPO, or "" where it has none."""
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/contents/{SIGNERS}?ref={sha}",
        headers={"Accept": "application/vnd.github.raw+json", "Authorization": "Bearer " + token,
                 "X-GitHub-Api-Version": "2022-11-28"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return ""
        raise


def main():
    with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as f:
        pull = json.load(f)["pull_request"]
    login = pull["user"]["login"]
    with open(SIGNERS, encoding="utf-8") as f:  # (main's: the workflow checks out main)
        listed = signers(f.read())
    if login.lower() not in listed:
        listed = signers(pull_copy(os.environ["GITHUB_REPOSITORY"], pull["head"]["sha"],
                                   os.environ["GITHUB_TOKEN"]))
    if login.lower() in listed:
        print(f"@{login} has certified the DCO in {SIGNERS}")
        return 0
    print(f"@{login} has not certified the DCO yet. After reading https://developercertificate.org/,"
          f" add this line to {SIGNERS} in this pull request (once: it covers your later ones too):\n"
          f"@{login} Your Name <your-email>\n"
          "Append \" for COMPANY\" if you contribute for your employer. CONTRIBUTING.md has the details.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
