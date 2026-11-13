"""ast_serialize as Pystachy compiles it: mypy's parser front end.

The API of ast_serialize 0.13.1 (https://pypi.org/project/ast-serialize/0.13.1/, the Rust
extension that mypy 2.4's native parser calls), in the subset: parse() tokenizes and parses a
Python source as its vendored Ruff parser does, with the same syntax errors and recovery, and
serializes the tree in mypy's binary format (mypy/nativeparse.py reads it); parse_type_string()
does the same for a string annotation. It follows ast_serialize's Rust source (src/*.rs, Copyright
(c) 2025-2026 Jukka Lehtosalo and contributors) and the Ruff crates it vendors
(crates/ruff_python_parser and ruff_python_ast, Copyright (c) 2022 Charles Marsh), both under the
MIT License; see THIRD_PARTY_NOTICES. The package works on the UTF-8 bytes of the source, so its
offsets are Ruff's byte offsets.
"""
import sys

from ._lexer import MODE_MODULE
from ._parser import Parser
from ._serialize import (
    LineIndex, Options, Serializer, SyntaxError_, extract_type_comments_and_ignores,
    resolve_overrides, serialize_imports,
)
from ._sha1 import sha1_hex

__all__ = ["parse", "parse_type_string"]


def _read_source(fnam: str) -> bytes:
    try:
        with open(fnam, "rb") as f:
            data = f.read()
    except OSError as e:
        raise ValueError(str(e.strerror) + " (os error " + str(e.errno) + ")")
    try:
        data.decode()
    except UnicodeDecodeError:
        raise ValueError("stream did not contain valid UTF-8")
    return data


def _error_dict(e: SyntaxError_) -> dict[str, int | str | bool]:
    d: dict[str, int | str | bool] = {}
    d["line"] = e.line
    d["column"] = e.column
    d["message"] = e.message
    d["blocker"] = e.blocker
    return d


def _ignore_list(items: list[tuple[int, list[bytes]]]) -> list[tuple[int, list[str]]]:
    out: list[tuple[int, list[str]]] = []
    for line, codes in items:
        out.append((line, [c.decode() for c in codes]))
    return out


def parse(
    fnam: str,
    source: str | bytes | None = None,
    skip_function_bodies: bool = False,
    python_version: tuple[int, int] | None = None,
    platform: str | None = None,
    always_true: list[str] | None = None,
    always_false: list[str] | None = None,
    cache_version: int = 0,
) -> tuple[bytes, list[dict[str, int | str | bool]], list[tuple[int, list[str]]], bytes, dict[str, object]]:
    if python_version is None:
        python_version = (sys.version_info[0], sys.version_info[1])
    if platform is None:
        platform = sys.platform
    if always_true is None:
        always_true = []
    if always_false is None:
        always_false = []
    if source is None:
        raw = _read_source(fnam)
    elif isinstance(source, str):
        raw = source.encode()
    else:
        raw = source
        raw.decode()
    return _parse_bytes(fnam, raw, skip_function_bodies,
                        Options(python_version, platform, always_true, always_false, cache_version))


def _parse_bytes(fnam: str, raw: bytes, skip_function_bodies: bool, options: Options):
    source_hash = sha1_hex(raw)
    if raw.find(b"\r") >= 0:
        text = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    else:
        text = raw
    li = LineIndex(text)
    slash = max(fnam.rfind("/"), fnam.rfind("\\") if sys.platform == "win32" else -1)
    is_stub_package = fnam[slash + 1:] == "__init__.pyi"
    p = Parser(text, MODE_MODULE)
    body = p.parse_module()
    errors: list[SyntaxError_] = []
    for i in range(len(p.err_start)):
        line = li.line_of(p.err_start[i])
        errors.append(SyntaxError_(line, li.column(line, p.err_start[i]), p.err_msg[i], True))
    comments = extract_type_comments_and_ignores(p, text, li, options)
    for e in comments.errors:
        errors.append(e)
    overrides = resolve_overrides(comments.mypy_comments)
    for name in overrides.always_true:
        options.always_true.append(name)
    for name in overrides.always_false:
        options.always_false.append(name)
    if overrides.ignore_errors == 1:
        skip_function_bodies = True
    type_ignores = comments.type_ignores
    mypy_ignores = comments.mypy_ignores
    top_unreachable = False
    has_first = False
    first_line = 0
    first_codes: list[bytes] = []
    if len(type_ignores) > 0 or len(mypy_ignores) > 0:
        has_first = True
        if len(type_ignores) == 0:
            first_line, first_codes = mypy_ignores[0]
        elif len(mypy_ignores) == 0:
            first_line, first_codes = type_ignores[0]
        elif type_ignores[0][0] < mypy_ignores[0][0]:
            first_line, first_codes = type_ignores[0]
        else:
            first_line, first_codes = mypy_ignores[0]
    first_statement_line = 0 if len(body) == 0 else li.line_of(body[0].start)
    if has_first and first_line < first_statement_line:
        top_unreachable = True
        type_ignores = []
        mypy_ignores = []
        if len(first_codes) > 0:
            joined = b", ".join(first_codes).decode()
            errors.append(SyntaxError_(
                first_line, 0,
                "Type ignore with error code is not supported for modules; use `# mypy: disable-error-code=\"" + joined + "\"`",
                False))
    ser = Serializer(text, li, options, skip_function_bodies, p, comments.type_comments)
    if top_unreachable:
        ser.tagged_int(0)
    else:
        ser.module(body)
    ast_bytes = ser.getvalue()
    import_bytes = serialize_imports(ser.imports, text, li)
    for e in ser.extra_errors:
        errors.append(e)
    skipped = ser.skipped_lines
    type_ignores = [t for t in type_ignores if t[0] not in skipped]
    mypy_ignores = [t for t in mypy_ignores if t[0] not in skipped]
    ast_data: dict[str, object] = {}
    ast_data["is_partial_package"] = is_stub_package and ser.top_level_getattr
    ast_data["mypy_ignores"] = _ignore_list(mypy_ignores)
    ast_data["uses_template_strings"] = ser.uses_template_strings
    ast_data["source_hash"] = source_hash
    ast_data["mypy_comments"] = [(line, t.decode()) for line, t in comments.mypy_comments]
    return (ast_bytes, [_error_dict(e) for e in errors], _ignore_list(type_ignores), import_bytes, ast_data)


def parse_type_string(source: str, range: tuple[int, int, int, int], cache_version: int = 0) -> bytes:
    ser = Serializer(b"", LineIndex(b""), Options((3, 10), "linux", [], [], cache_version), False, None, {})
    ser.is_evaluated = False
    ser.override = True
    ser.o_line = range[0]
    ser.o_col = range[1]
    ser.o_end_line = range[2]
    ser.o_end_col = range[3]
    ser.string_type(source.encode(), 0, 0)
    return ser.getvalue()
