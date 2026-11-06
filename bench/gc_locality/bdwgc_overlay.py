#!/usr/bin/env python3
"""Create an explicitly optional BDWGC runtime overlay; never edit a source tree.

The dependency is supplied by the caller, not downloaded or enabled implicitly.
The emitted manifest pins source, adapter, public headers and linked library bytes.
Use its environment with the *same* native compiler used for the native baseline.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def function_body(source, name, body):
    """Replace one C function body, ignoring braces inside comments/literals."""
    pattern = re.compile(r"^[^\n;{}]*\b" + re.escape(name) + r"\([^\n;{}]*?\)[ \t]*\{", re.M)
    matches = list(pattern.finditer(source))
    if len(matches) != 1:
        raise ValueError(f"expected exactly one function definition for {name}; found {len(matches)}")
    start = matches[0].end()
    # Tokens consume comments and quoted literals before matching real braces.
    tokens = re.compile(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|[{}]', re.S)
    depth = 1
    for token in tokens.finditer(source, start):
        if token.group() == "{":
            depth += 1
        elif token.group() == "}":
            depth -= 1
            if depth == 0:
                return source[:start] + "\n" + body.strip() + "\n" + source[token.start():]
    raise ValueError(f"unclosed function: {name}")


def adapt(source, adapter):
    replacements = {
        "collect": "  GC_gcollect();",
        "gc_slow": "  return bdw_alloc(n, how);",
        "gc_alloc": "  return bdw_alloc(n, atomic);",
        "gc_init": "  bdw_init(sb, roots, nroots);",
        "gc_report": "  bdw_report();",
        "atomic_items": """
  if (a == empty_atomic) return 1;
  void *base = GC_base((void *)a);
  return base && GC_get_kind_and_size(base, NULL) == bdw_atomic_kind;
""",
        "str_grow": """
  void *base = GC_base(s);
  int big = base && GC_size(base) >= SMALL;
  Str *r = gc_raw(owned && big ? 2 * m : m);
  r->len = s->len; r->dict_hash = 0; memcpy(r->s, s->s, s->len); return r;
""",
        "pys_str_iadd": """
  I n = s->len + t->len, m = (I)sizeof(Str) + n + 1, chars1 = text_cat_count(s->chars1, s->len, t);
  void *base = owned ? GC_base(s) : NULL;
  if (!base || (uint64_t)m > GC_size(base) - 1) s = str_grow(s, m, owned);
  else if (s->chars1 != s->len + 1) {
    TextHint *hint = text_hint_slot(s);
    if (hint->s == s) hint->s = 0;
  }
  memcpy(s->s + s->len, t->s, t->len); s->s[n] = 0; s->len = n; s->chars1 = chars1; return s;
""",
        "pys_weakref_new": '  bdw_unsupported("weak references and weak-reference callbacks");',
        "pys_open": '  bdw_unsupported("managed file resources");',
        "pys_bopen": '  bdw_unsupported("managed binary file resources");',
        "pys_track": '  bdw_unsupported("CPython ownership tracking");',
        "pys_init_lib": '  bdw_unsupported("CPython extension embedding");',
    }
    for name, body in replacements.items():
        source = function_body(source, name, body)
    anchor = "__attribute__((noinline)) static void collect(void) {"
    if source.count(anchor) != 1:
        raise ValueError("collect declaration changed; inspect integration before adapting")
    return source.replace(anchor, adapter + "\n" + anchor), list(replacements)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="Pystachy checkout whose runtime is adapted")
    parser.add_argument("--output", type=Path, required=True, help="new overlay directory (must not exist)")
    parser.add_argument("--include", type=Path, required=True, help="directory containing gc/gc.h")
    parser.add_argument("--library", type=Path, required=True, help="exact libgc.a or shared-library file")
    args = parser.parse_args()
    source, output = args.source.resolve(), args.output.absolute()
    include, library = args.include.resolve(), args.library.resolve()
    if output.exists():
        parser.error("--output must not exist; do not overwrite an existing overlay")
    if output.is_relative_to(source):
        parser.error("place --output outside the source tree")
    if any(c.isspace() for c in str(include) + str(library)):
        parser.error("PYSTACHY_CFLAGS splits on whitespace; dependency paths must contain none")
    headers = {str(p.relative_to(include)): digest(p) for p in sorted((include / "gc").glob("*.h"))}
    if "gc/gc.h" not in headers or "gc/gc_mark.h" not in headers or not library.is_file():
        parser.error("BDWGC public headers and library are required")
    adapter = HERE / "bdwgc_adapter.c"
    runtime = source / "runtime.c"
    identity = {"source_runtime_sha256": digest(runtime), "adapter_sha256": digest(adapter),
                "headers_sha256": headers, "library_sha256": digest(library)}
    # Include identities in runtime bytes because the normal driver does not hash
    # third-party headers/libraries. A changed dependency must get a new cache key.
    code, functions = adapt(runtime.read_text(), adapter.read_text())
    code = "/* BDWGC research overlay inputs: " + json.dumps(identity, sort_keys=True) + " */\n" + code
    output.mkdir(parents=True)
    for entry in source.iterdir():
        if entry.name not in {"runtime.c", "build", ".git"}:
            (output / entry.name).symlink_to(entry, target_is_directory=entry.is_dir())
    (output / "runtime.c").write_text(code)
    flags = f"-I{include} {library}"
    if library.suffix != ".a":
        flags += f" -Wl,-rpath,{library.parent}"
    manifest = {"schema": 1, "backend": "bdwgc-restricted-aot", "inputs": identity,
                "source": str(source), "include": str(include), "library": str(library),
                "overlay": str(output), "overlay_runtime_sha256": digest(output / "runtime.c"),
                "replaced_functions": functions,
                "environment": {"PYSTACHY_HOME": str(output), "PYSTACHY_CACHE": str(output / "build"),
                                "PYSTACHY_CFLAGS": flags}}
    (output / "bdwgc-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps(manifest, indent=2))


if __name__ == "__main__":
    main()
