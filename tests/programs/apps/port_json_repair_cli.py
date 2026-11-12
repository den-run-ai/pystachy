# The port's own command (json_repair.__main__), then upstream's (json_repair.json_repair.cli()):
# indented output, a named output file, inline replacement, its options, and the errors it reports
# itself. The port keeps upstream's in json_repair._cli, which a program that runs it imports. One
# program runs both: each loads argparse and re, whose code the Lean corpus checks would prove twice.
import os
import tempfile
from json_repair.__main__ import cli
from json_repair._cli import cli as upstream
from json_repair.json_repair import cli as facade


def text(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def upstream_command() -> None:
    directory = tempfile.mkdtemp()
    source = os.path.join(directory, "source.json")
    target = os.path.join(directory, "target.json")
    schema = os.path.join(directory, "schema.json")
    with open(source, "w", encoding="utf-8") as f:
        f.write('{name: "café", items: [1, 2, 3,], nested: {a: tru, b: nul}, empty: [], none: {}}')
    with open(schema, "w", encoding="utf-8") as f:
        f.write('{"type": "object"}')
    print(upstream([source]))
    print(facade([source, "--indent", "0"]))
    print(upstream([source, "--indent", "4", "--ensure_ascii"]))
    print(upstream([source, "-o", target]), repr(text(target)))
    print(upstream([source, "--output", target, "--indent", "1", "--skip-json-loads"]), repr(text(target)))
    with open(target, "w", encoding="utf-8") as f:
        f.write('{"a": 1, "a": 2, "b": [1 2]}')
    print(upstream([target, "-i"]), repr(text(target)))
    with open(target, "w", encoding="utf-8") as f:
        f.write('{"a": 1, "a": 2}')
    print(upstream([target, "--strict"]), repr(text(target)))
    for argv in [[source, "-i", "-o", target], ["-i"], [source, "--schema", schema, "--schema-model", "m:C"],
                 [source, "--strict", "--schema", schema], [source, "--schema-repair-mode", "salvage"]]:
        try:
            print(upstream(argv))
        except SystemExit as e:
            print("exit", str(e))
    print(upstream([os.path.join(directory, "missing.json")]))
    print(upstream([source, "--schema", schema]))  # (the port's schema stand-in: PORT.md)
    print(text(source) == '{name: "café", items: [1, 2, 3,], nested: {a: tru, b: nul}, empty: [], none: {}}')
    os.remove(schema)
    os.remove(target)
    os.remove(source)
    os.rmdir(directory)



# (upstream's first: the recorded stderr line stays the own command's last, as before)
upstream_command()
directory = tempfile.mkdtemp()
source = os.path.join(directory, "source.json")
target = os.path.join(directory, "target.json")
with open(source, "w", encoding="utf-8") as f:
    f.write('{name: "café", values: [true, null,],}')
print(cli([source, "-o", target, "--ensure_ascii"]))
with open(source, encoding="utf-8") as f:
    print(f.read())
with open(target, encoding="utf-8") as f:
    print(f.read())
print(cli(["--inline", source]))
with open(source, encoding="utf-8") as f:
    print(f.read())
with open(source, "wb") as binary_output:
    binary_output.write(br'{"value":"\ud800"}')
print(cli(["--inline", source]))
with open(source, "rb") as binary_input:
    print(binary_input.read())
os.remove(target)
os.remove(source)
os.rmdir(directory)
