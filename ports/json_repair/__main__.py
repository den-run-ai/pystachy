# pystachy: dynamic-any
"""File and pipe interface for the schema-free json_repair port."""
import argparse
import json
import sys

from .json_repair import loads


def cli(inline_args: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="json_repair", description="Repair and parse JSON files.")
    parser.add_argument("filename", nargs="?", help="Read from this file instead of stdin")
    parser.add_argument("-i", "--inline", action="store_true", help="Replace the input file")
    parser.add_argument("-o", "--output", metavar="TARGET", help="Write to TARGET instead of stdout")
    parser.add_argument("--ensure_ascii", action="store_true", help="Escape non-ASCII characters")
    parser.add_argument("--skip-json-loads", action="store_true", help="Skip initial JSON validation")
    parser.add_argument("--strict", action="store_true", help="Raise on structural repair errors")
    args = parser.parse_args(inline_args)

    filename = args.filename or None
    target = args.output or None
    if args.inline:
        if filename is None:
            print("Error: Inline mode requires a filename", file=sys.stderr)
            return 1
        if target is not None:
            print("Error: You cannot pass both --inline and --output", file=sys.stderr)
            return 1
        target = filename

    try:
        if filename is None:
            text = sys.stdin.read()
        else:
            with open(filename, encoding="utf-8") as source:
                text = source.read()
        result = loads(text, skip_json_loads=args.skip_json_loads, strict=args.strict)
        encoded = json.dumps(result, ensure_ascii=args.ensure_ascii)
        if target is None:
            print(encoded)
        else:
            with open(target, "w", encoding="utf-8") as output:
                output.write(encoded)
    except (OSError, TypeError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(cli())
