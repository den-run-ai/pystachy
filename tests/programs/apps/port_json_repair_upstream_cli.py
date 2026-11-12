# pystachy: dynamic-any
# Upstream's own command, json_repair.json_repair.cli(): indented output, a named output file,
# inline replacement, its options, and the errors it reports itself. The port keeps it in
# json_repair._cli, which a program that runs the command imports.
import os
import tempfile

from json_repair._cli import cli
from json_repair.json_repair import cli as facade


def text(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def main() -> None:
    directory = tempfile.mkdtemp()
    source = os.path.join(directory, "source.json")
    target = os.path.join(directory, "target.json")
    schema = os.path.join(directory, "schema.json")
    with open(source, "w", encoding="utf-8") as f:
        f.write('{name: "café", items: [1, 2, 3,], nested: {a: tru, b: nul}, empty: [], none: {}}')
    with open(schema, "w", encoding="utf-8") as f:
        f.write('{"type": "object"}')
    print(cli([source]))
    print(facade([source, "--indent", "0"]))
    print(cli([source, "--indent", "4", "--ensure_ascii"]))
    print(cli([source, "-o", target]), repr(text(target)))
    print(cli([source, "--output", target, "--indent", "1", "--skip-json-loads"]), repr(text(target)))
    with open(target, "w", encoding="utf-8") as f:
        f.write('{"a": 1, "a": 2, "b": [1 2]}')
    print(cli([target, "-i"]), repr(text(target)))
    with open(target, "w", encoding="utf-8") as f:
        f.write('{"a": 1, "a": 2}')
    print(cli([target, "--strict"]), repr(text(target)))
    for argv in [[source, "-i", "-o", target], ["-i"], [source, "--schema", schema, "--schema-model", "m:C"],
                 [source, "--strict", "--schema", schema], [source, "--schema-repair-mode", "salvage"]]:
        try:
            print(cli(argv))
        except SystemExit as e:
            print("exit", str(e))
    print(cli([os.path.join(directory, "missing.json")]))
    print(cli([source, "--schema", schema]))  # (the port's schema stand-in: PORT.md)
    print(text(source) == '{name: "café", items: [1, 2, 3,], nested: {a: tru, b: nul}, empty: [], none: {}}')
    os.remove(schema)
    os.remove(target)
    os.remove(source)
    os.rmdir(directory)


main()
