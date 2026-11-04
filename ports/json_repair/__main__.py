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
            # CPython's standard input can represent malformed bytes as surrogates.
            raw = sys.stdin.read().encode("utf-8", "surrogateescape")
        else:
            with open(filename, "rb") as source:
                raw = source.read()
        text = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
        result = loads(text, skip_json_loads=args.skip_json_loads, strict=args.strict)
        encoded = json.dumps(result, ensure_ascii=args.ensure_ascii)
        # A JSON escape can decode to a lone surrogate. Check before truncating a file.
        payload = encoded.encode("utf-8")
        if target is None:
            print(encoded)
        else:
            with open(target, "wb") as output:
                output.write(payload)
    except (OSError, TypeError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(cli())
