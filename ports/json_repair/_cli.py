# pystachy: dynamic-any
"""Pystachy port: upstream's command, which json_repair.json_repair.cli() runs.

The function is upstream's cli(), unchanged but for the two marked lines. It is in a module of
its own so that importing json_repair loads neither argparse nor pathlib.
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .json_repair import from_file, loads
from .schema_repair import load_schema_model


def cli(inline_args: list[str] | None = None) -> int:
    """
    Command-line interface for repairing and parsing JSON files.

    Args:
        inline_args (Optional[List[str]]): List of command-line arguments for testing purposes. Defaults to None.
            - filename (str): The JSON file to repair. If omitted, the JSON is read from stdin.
            - -i, --inline (bool): Replace the file inline instead of returning the output to stdout.
            - -o, --output TARGET (str): If specified, the output will be written to TARGET filename instead of stdout.
            - --ensure_ascii (bool): Pass ensure_ascii=True to json.dumps(). Will pass False otherwise.
            - --indent INDENT (int): Number of spaces for indentation (Default 2).
            - --skip-json-loads (bool): Skip initial json.loads validation.
            - --schema SCHEMA (str): Path to a JSON Schema file that guides repairs.
            - --schema-model MODEL (str): Pydantic v2 model in 'module:ClassName' form that guides repairs.
            - --strict (bool): Raise on duplicate keys, missing separators, empty keys/values, and other unrecoverable structures instead of repairing them.

    Returns:
        int: Exit code of the CLI operation.

    Raises:
        Exception: Any exception that occurs during file processing.

    Example:
        >>> cli(['example.json', '--indent', '4'])
        >>> cat json.txt | json_repair
    """
    parser = argparse.ArgumentParser(description="Repair and parse JSON files.")
    # Make the filename argument optional; if omitted, we will read from stdin.
    parser.add_argument(
        "filename",
        nargs="?",
        help="The JSON file to repair (if omitted, reads from stdin)",
    )
    parser.add_argument(
        "-i",
        "--inline",
        action="store_true",
        help="Replace the file inline instead of returning the output to stdout",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="TARGET",
        help="If specified, the output will be written to TARGET filename instead of stdout",
    )
    parser.add_argument(
        "--ensure_ascii",
        action="store_true",
        help="Pass ensure_ascii=True to json.dumps()",
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="Number of spaces for indentation (Default 2)",
    )
    parser.add_argument(
        "--skip-json-loads",
        action="store_true",
        help="Skip initial json.loads validation",
    )
    parser.add_argument(
        "--schema",
        metavar="SCHEMA",
        help="Path to a JSON Schema file that guides repairs",
    )
    parser.add_argument(
        "--schema-model",
        metavar="MODEL",
        help="Pydantic v2 model in 'module:ClassName' form that guides repairs",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Raise on duplicate keys, missing separators, empty keys/values, and other unrecoverable structures instead of repairing them",
    )
    parser.add_argument(
        "--schema-repair-mode",
        choices=["standard", "salvage"],
        default="standard",
        help="Schema repair mode: 'standard' (default) or 'salvage' (best-effort array/object salvage).",
    )

    args = parser.parse_args(inline_args)

    # Inline mode requires a filename, so error out if none was provided.
    if args.inline and not args.filename:  # pragma: no cover
        print("Error: Inline mode requires a filename", file=sys.stderr)
        sys.exit(1)

    if args.inline and args.output:  # pragma: no cover
        print("Error: You cannot pass both --inline and --output", file=sys.stderr)
        sys.exit(1)

    if args.schema and args.schema_model:
        print("Error: You cannot pass both --schema and --schema-model", file=sys.stderr)
        sys.exit(1)

    if args.strict and (args.schema or args.schema_model):
        print("Error: --strict cannot be used with --schema or --schema-model", file=sys.stderr)
        sys.exit(1)
    if args.schema_repair_mode == "salvage" and not (args.schema or args.schema_model):
        print("Error: --schema-repair-mode salvage requires --schema or --schema-model", file=sys.stderr)
        sys.exit(1)

    ensure_ascii = args.ensure_ascii

    try:
        schema: Any = None  # Pystachy port: declared, so that json.load() decodes into Any values
        if args.schema:
            with Path(args.schema).open() as fd:
                schema = json.load(fd)
        elif args.schema_model:
            schema = load_schema_model(args.schema_model)

        # Use from_file if a filename is provided; otherwise read from stdin.
        if args.filename:
            result = from_file(
                args.filename,
                skip_json_loads=args.skip_json_loads,
                strict=args.strict,
                schema=schema,
                schema_repair_mode=args.schema_repair_mode,
            )
        else:
            data = sys.stdin.read()
            result = loads(
                data,
                skip_json_loads=args.skip_json_loads,
                strict=args.strict,
                schema=schema,
                schema_repair_mode=args.schema_repair_mode,
            )
        if args.inline or args.output:
            # Pystachy port: "" for the type of the path (inline mode has a filename: see above)
            with Path(args.output or args.filename or "").open(mode="w") as fd:
                json.dump(result, fd, indent=args.indent, ensure_ascii=ensure_ascii)
        else:
            print(json.dumps(result, indent=args.indent, ensure_ascii=ensure_ascii))
    except (OSError, TypeError, ValueError) as e:  # pragma: no cover
        print(f"Error: {e!s}", file=sys.stderr)
        return 1

    return 0  # Success
