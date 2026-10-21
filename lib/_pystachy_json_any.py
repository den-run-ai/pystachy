# pystachy: dynamic-any
"""json.loads() and json.dumps() of Any values (#779).

In a module that compiles typing.Any as dynamic values (docs/dynamic-any.md), the compiler calls
loads() here for json.loads() where its result becomes an Any value, and dumps() here for
json.dumps() of a value that holds Any values. loads() decodes straight into Any's containers
(list[Any], dict[str, Any]), so the document is the one object that both typed and Any code
then share; dumps() walks Any values as CPython's encoder walks objects: tuples are arrays, int,
float, bool and None keys become strings, and a value JSON cannot hold raises its TypeError.
json's own functions keep JSONValue's typed storage for other code. The text scanner, its errors
and limits are json's (_Parser): strings, keys, numbers, 64-bit integers, 256 levels of nesting.
"""
from typing import Any

from json import JSONDecodeError, _Parser, _quote


def _value(p: _Parser, depth: int) -> Any:
    i = p.pos
    if i == p.n:
        raise p.error("Expecting value", i)
    c = p.data[i]
    if c == 34:
        return p.string()
    if c == 91 or c == 123:
        if depth >= 256:
            raise RecursionError("maximum JSON nesting depth exceeded")
        if c == 91:
            return _array(p, depth)
        return _object(p, depth)
    v = p.value(depth)  # (a number or a constant: one of json's scalars)
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return v
    return None


def _array(p: _Parser, depth: int) -> list[Any]:
    data = p.data
    p.pos += 1
    p.skip()
    out: list[Any] = []
    if p.pos < p.n and data[p.pos] == 93:
        p.pos += 1
        return out
    while True:
        out.append(_value(p, depth + 1))
        p.skip()
        i = p.pos
        if i < p.n and data[i] == 93:
            p.pos = i + 1
            return out
        if i == p.n or data[i] != 44:
            raise p.error("Expecting ',' delimiter", i)
        p.pos = i + 1
        p.skip()
        if p.pos < p.n and data[p.pos] == 93:
            raise p.error("Illegal trailing comma before end of array", i)


def _object(p: _Parser, depth: int) -> dict[str, Any]:
    data = p.data
    p.pos += 1
    p.skip()
    out: dict[str, Any] = {}
    if p.pos < p.n and data[p.pos] == 125:
        p.pos += 1
        return out
    while True:
        i = p.pos
        if i == p.n or data[i] != 34:
            raise p.error("Expecting property name enclosed in double quotes", i)
        key = p.key()
        p.skip()
        i = p.pos
        if i == p.n or data[i] != 58:
            raise p.error("Expecting ':' delimiter", i)
        p.pos = i + 1
        p.skip()
        out[key] = _value(p, depth + 1)
        p.skip()
        i = p.pos
        if i < p.n and data[i] == 125:
            p.pos = i + 1
            return out
        if i == p.n or data[i] != 44:
            raise p.error("Expecting ',' delimiter", i)
        p.pos = i + 1
        p.skip()
        if p.pos < p.n and data[p.pos] == 125:
            raise p.error("Illegal trailing comma before end of object", i)


def _parse(p: _Parser) -> Any:
    data = p.data
    if p.n >= 3 and data[0] == 0xEF and data[1] == 0xBB and data[2] == 0xBF:
        raise JSONDecodeError("Unexpected UTF-8 BOM (decode using utf-8-sig)", p.doc, 0)
    p.skip()
    value = _value(p, 0)
    p.skip()
    if p.pos != p.n:
        raise p.error("Extra data", p.pos)
    return value


def loads(s: str) -> Any:
    """Decode JSON text into Any values: its arrays are list[Any], its objects dict[str, Any]."""
    try:
        return _parse(_Parser(s, False))
    except UnicodeDecodeError:
        return _parse(_Parser(s, True))


def _floatstr(value: float, allow_nan: bool) -> str:
    if value != value or value == float("inf") or value == -float("inf"):
        if not allow_nan:
            raise ValueError("Out of range float values are not JSON compliant: " + repr(value))
        return "NaN" if value != value else "Infinity" if value > 0.0 else "-Infinity"
    return repr(value)


class _Writer:
    def __init__(self, skipkeys: bool, ensure_ascii: bool, check_circular: bool, allow_nan: bool,
                 sort_keys: bool, item_separator: str, key_separator: str, default: Any) -> None:
        self.skipkeys = skipkeys
        self.ascii = ensure_ascii
        self.circular = check_circular
        self.nan = allow_nan
        self.sort_keys = sort_keys
        self.item_separator = item_separator
        self.key_separator = key_separator
        self.default = default
        self.out: list[str] = []
        self.calls = 0  # (default() calls so far: where one ran, a dict being written may have changed)
        self.open: list[Any] = []  # (the containers being written, for check_circular)

    def enter(self, value: Any, depth: int) -> None:
        if self.circular:
            for parent in self.open:
                if value is parent:
                    raise ValueError("Circular reference detected")
        if depth >= 256:
            raise RecursionError("maximum JSON nesting depth exceeded")
        self.open.append(value)

    def key(self, k: Any) -> str:
        # an object key as a string: CPython's conversions, or "" where skipkeys skips it
        if isinstance(k, str):
            return k
        if k is True:
            return "true"
        if k is False:
            return "false"
        if k is None:
            return "null"
        if isinstance(k, int):
            return str(k)
        if isinstance(k, float):
            return _floatstr(k, self.nan)
        if self.skipkeys:
            return ""
        raise TypeError(f"keys must be str, int, float, bool or None, not {type(k).__name__}")

    def write(self, value: Any, depth: int) -> None:
        out = self.out
        if value is None:
            out.append("null")
        elif value is True:
            out.append("true")
        elif value is False:
            out.append("false")
        elif isinstance(value, str):
            _quote(out, value, self.ascii)
        elif isinstance(value, int):
            out.append(str(value))
        elif isinstance(value, float):
            out.append(_floatstr(value, self.nan))
        elif isinstance(value, list) or isinstance(value, tuple):
            self.enter(value, depth)
            out.append("[")
            first = True
            for item in value:
                if not first:
                    out.append(self.item_separator)
                first = False
                self.write(item, depth + 1)
            out.append("]")
            self.open.pop()
        elif isinstance(value, dict):
            self.enter(value, depth)
            out.append("{")
            first = True
            if self.sort_keys:
                # (CPython sorts a list of the items first: a default() callback's change to a
                # value is not seen)
                for k, v in sorted(value.items()):
                    if self.entry(k, v, first, depth):
                        first = False
            else:
                # as CPython's encoder walks a dict (PyDict_Next): each value is read when its key is
                # reached, so a default() callback's change to a later entry is seen, a key it
                # deletes is skipped and one it adds is written after the others (where no callback
                # ran, the dict is as it was)
                keys = list(value)
                calls = self.calls
                i = 0
                while i < len(keys):
                    k = keys[i]
                    i += 1
                    if (self.calls == calls or k in value) and self.entry(k, value[k], first, depth):
                        first = False
                    if i == len(keys) and self.calls != calls:
                        seen = {x: True for x in keys}
                        keys.extend([x for x in value if x not in seen])
            out.append("}")
            self.open.pop()
        elif self.default is not None:
            self.enter(value, depth)
            self.calls += 1
            self.write(self.default(value), depth + 1)
            self.open.pop()
        else:
            raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")

    def entry(self, k: Any, v: Any, first: bool, depth: int) -> bool:
        # writes k: v of a dict, after an item separator unless first; False where skipkeys
        # skips k, which writes nothing
        out = self.out
        if k is not None and not isinstance(k, (str, int, float)) and self.skipkeys:
            return False
        s = self.key(k)
        if not first:
            out.append(self.item_separator)
        _quote(out, s, self.ascii)
        out.append(self.key_separator)
        self.write(v, depth + 1)
        return True


def dumps(obj: Any, *, skipkeys: bool = False, ensure_ascii: bool = True, check_circular: bool = True,
          allow_nan: bool = True, separators: tuple[str, str] | None = None, default: Any = None,
          sort_keys: bool = False) -> str:
    """Encode Any values, as CPython's json.dumps() without indent and cls."""
    item_separator = ", "
    key_separator = ": "
    if separators is not None:
        item_separator = separators[0]
        key_separator = separators[1]
    w = _Writer(skipkeys, ensure_ascii, check_circular, allow_nan, sort_keys, item_separator, key_separator, default)
    w.write(obj, 0)
    return "".join(w.out)
