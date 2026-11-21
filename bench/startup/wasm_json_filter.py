"""Count open issues in a host tool's JSON response using the typed decoder."""
import json

from codemode import call


def count_open_issues() -> int:
    issues = json.loads(call("issue_records", "pystachy"))
    opened = 0
    if isinstance(issues, list):
        for issue in issues:
            if isinstance(issue, dict):
                state = issue["state"]
                if isinstance(state, str) and state == "open":
                    opened += 1
            else:
                raise TypeError("expected an issue object")
        return opened
    raise TypeError("expected an array of issues")
