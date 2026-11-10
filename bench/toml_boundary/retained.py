"""AOT-only collection probe; use the benchmark's force-included C header."""
import sys
import tomllib
from ffi import c_int64, extern
from consumer import document, exercise, score


@extern("")
def toml_boundary_collect_live() -> c_int64:
    ...


source = document(int(sys.argv[1]))
rounds = int(sys.argv[2])
print("checksum", exercise(source, rounds))
held = tomllib.loads(source)
live = toml_boundary_collect_live()
# Use the document after collection so it remains a live root at the sample.
print("retained", live, score(held))
