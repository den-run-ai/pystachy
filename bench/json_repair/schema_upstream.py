"""Run schema.py against unmodified jsonschema and upstream json_repair.

Only two import module paths change. Fixtures, operations, error messages,
timers and correctness checks are the same source as the native/adapted probe.
Use PYTHONPATH pointing at pristine upstream's src directory.
"""
from pathlib import Path


source_path = Path(__file__).with_name("schema.py")
source = source_path.read_text()
for suffix in ("exceptions", "validators"):
    original = f"from json_repair._jsonschema.{suffix} import "
    replacement = f"from jsonschema.{suffix} import "
    if source.count(original) != 1:
        raise ValueError("schema benchmark backend import changed")
    source = source.replace(original, replacement)
exec(compile(source, str(source_path), "exec"), {"__name__": "__main__", "__file__": str(source_path)})
