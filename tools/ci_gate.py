"""Classify the PR merge tree and require the jobs selected by its CI plan."""

import argparse
import subprocess
import sys


def verification_plan(event: str, base: str) -> str:
    if event != "pull_request":
        return "code"
    # Checkout's depth of two includes the first parent of the tested merge commit.
    if subprocess.check_output(["git", "rev-parse", "HEAD^1"], text=True).strip() != base:
        raise ValueError("The tested merge commit does not have the expected PR base")
    paths = subprocess.check_output(
        ["git", "diff", "--name-only", "--no-renames", "-z", base, "HEAD", "--"]
    ).split(b"\0")[:-1]
    if paths and all(path.endswith(b".md") or path.startswith(b"docs/") for path in paths):
        return "docs"
    return "code"


def require_jobs(event: str, plan: str, arm_plan: str, results: list[str]) -> None:
    if plan != arm_plan or plan not in ("docs", "code"):
        raise ValueError(f"Missing or inconsistent CI plans: {plan!r}, {arm_plan!r}")
    pr = event == "pull_request"
    if plan == "docs" and not pr:
        raise ValueError("Only a pull request can use the documentation-only plan")
    expected = ["success", "success", "success" if pr else "skipped", "success" if pr else "skipped"]
    if plan == "docs":
        expected = ["success", "skipped", "skipped", "skipped"]
    for name, result, wanted in zip(("bootstrap", "verification", "pr-variants", "distribution"),
                                    results, expected, strict=True):
        if result != wanted:
            raise ValueError(f"{plan} plan requires {name}={wanted}, got {result!r}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan")
    plan.add_argument("event")
    plan.add_argument("base")
    gate = commands.add_parser("require-jobs")
    gate.add_argument("event")
    gate.add_argument("plan")
    gate.add_argument("arm_plan")
    gate.add_argument("results", nargs=4)
    args = parser.parse_args()
    try:
        if args.command == "plan":
            print(verification_plan(args.event, args.base))
        else:
            require_jobs(args.event, args.plan, args.arm_plan, args.results)
    except (OSError, subprocess.CalledProcessError, ValueError) as error:
        print(f"CI verification: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
