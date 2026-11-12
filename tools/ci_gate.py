"""Classify the PR merge tree and require the jobs selected by its CI plan."""

import argparse
import re
import subprocess
import sys


def verification_plan(event: str, base: str, commit: str, head: str) -> str:
    if event != "pull_request":
        return "code"
    for name, value in (("base", base), ("commit", commit), ("head", head)):
        if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value):
            raise ValueError(f"Missing or invalid event PR {name}")
    # Check the immutable event merge and PR head before trusting either parent.
    # Depth two includes both parents, even if the base event payload is stale.
    tested = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    if tested != commit:
        raise ValueError("The tested commit does not match the event merge commit")
    parents = subprocess.check_output(["git", "show", "-s", "--format=%P", "HEAD"], text=True).split()
    if len(parents) != 2:
        raise ValueError("The tested PR commit must have exactly two parents")
    if parents[1] != head:
        raise ValueError("The tested merge commit does not have the expected PR head")
    if parents[0] != base:
        # GitHub can generate the event merge against a newer base than the PR
        # payload records. Never allow that mismatch to skip code verification.
        return "code"
    paths = subprocess.check_output(
        ["git", "diff", "--name-only", "--no-renames", "-z", base, "HEAD", "--"]
    ).split(b"\0")[:-1]
    if paths and all(path.endswith(b".md") or path.startswith(b"docs/") for path in paths):
        return "docs"
    return "code"


def require_jobs(event: str, plan: str, arm_plan: str, results: list[str]) -> None:
    pr = event == "pull_request"
    if plan not in ("docs", "code") or arm_plan != ("" if pr else plan):
        raise ValueError(f"Missing or inconsistent CI plans: {plan!r}, {arm_plan!r}")
    if plan == "docs" and not pr:
        raise ValueError("Only a pull request can use the documentation-only plan")
    expected = ["success", "success", "success" if pr else "skipped", "skipped" if pr else "success"]
    if plan == "docs":
        expected = ["success", "skipped", "skipped", "skipped"]
    for name, result, wanted in zip(("bootstrap", "verification", "pr-variants", "qualification"),
                                    results, expected, strict=True):
        if result != wanted:
            raise ValueError(f"{plan} plan requires {name}={wanted}, got {result!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan")
    plan.add_argument("event")
    plan.add_argument("base")
    plan.add_argument("commit")
    plan.add_argument("head")
    gate = commands.add_parser("require-jobs")
    gate.add_argument("event")
    gate.add_argument("plan")
    gate.add_argument("arm_plan")
    gate.add_argument("results", nargs=4)
    args = parser.parse_args()
    try:
        if args.command == "plan":
            print(verification_plan(args.event, args.base, args.commit, args.head))
        else:
            require_jobs(args.event, args.plan, args.arm_plan, args.results)
    except (OSError, subprocess.CalledProcessError, ValueError) as error:
        print(f"CI verification: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
