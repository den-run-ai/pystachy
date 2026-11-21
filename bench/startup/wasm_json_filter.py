"""Count open issues in a host tool's JSON response using the typed decoder."""
import json

from codemode import call


def count_open_issues() -> int:
    issues = json.loads(call("issue_records", "pystachy"))
    if not isinstance(issues, list):
        raise TypeError("expected an array of issues")
    opened = 0
    for issue in issues:
        if not isinstance(issue, dict):
            raise TypeError("expected an issue object")
        state = issue["state"]
        if isinstance(state, str) and state == "open":
            opened += 1
    return opened
