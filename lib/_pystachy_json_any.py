# pystachy: dynamic-any
"""json.loads() and json.dumps() of Any values (#779).

In a module that compiles typing.Any as dynamic values (docs/dynamic-any.md), the compiler calls
loads() here for json.loads() where its result becomes an Any value, and dumps() here for
json.dumps() of a value that holds Any values. loads() decodes straight into Any's containers
(list[Any], dict[str, Any]), so the document is the one object that both typed and Any code
then share; dumps() walks Any values as CPython's encoder walks objects: tuples are arrays, int,
float, bool and None keys become strings, and a value JSON cannot hold raises its TypeError.
json's own functions keep JSONValue's typed storage for other code. The text scanner, its errors
and limits are json's (_Parser): strings, keys, number syntax and its bounds on nesting.
Integer tokens beyond int64 promote through a separate helper; scanner indices stay fixed-width.
"""
from typing import Any, TextIO

from json import _ARRAY_TOKEN, _OBJECT_TOKEN, _Parser, _STRING_TOKEN, _quote
from _pystachy_json_int import _integer


def _value(p: _Parser, depth: int) -> Any:
    token = p.next_token()
    if token is _STRING_TOKEN:
        return p.string()
    if token is _ARRAY_TOKEN or token is _OBJECT_TOKEN:
        if depth >= 64:  # (as json's _Parser.value(): the containers nested further are decoded without calls)
            return _deep(p, token is _ARRAY_TOKEN, depth)
        if token is _ARRAY_TOKEN:
            return _array(p, depth)
        return _object(p, depth)
    v = p.scalar_value()  # a number, constant, or an overflowing integer token
    if isinstance(v, bool):
        return v
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return v
    if isinstance(v, str):
        return _integer(v)
    return None


def _deep(p: _Parser, array: bool, depth: int) -> Any:
    # The container at depth and all that it holds, with the open containers on a list where
    # _array() and _object() have them in calls: nesting past the first 64 uses neither the
    # recursion limit nor the native stack, and stops where CPython's decoder does, at 9,998.
    # The scanner's deep_*() methods are its begin(), next_item() and object_key().
    arrays: list[bool] = []
    outer: list[Any] = []
    keys: list[str] = []
    current: Any = None
    while True:
        # open a container of the kind array says, inside current
        if depth >= 9998:
            raise RecursionError("maximum recursion depth exceeded while decoding a JSON "
                                 + ("array" if array else "object") + " from a unicode string")
        if len(arrays) > 0:
            outer.append(current)
        arrays.append(array)
        if array:
            current = []
        else:
            current = {}
        depth += 1
        more = not p.deep_begin(array)
        while True:
            array = arrays[-1]
            if more:
                key = "" if array else p.deep_key()
                opener = p.deep_token()
                if opener is _ARRAY_TOKEN or opener is _OBJECT_TOKEN:
                    keys.append(key)
                    array = opener is _ARRAY_TOKEN
                    break
                item = _value(p, 0)  # (no container: a scalar, or the error for none)
                if array:
                    current.append(item)
                else:
                    current[key] = item
            else:
                # current is closed: it is the value, or an item of the container around it
                arrays.pop()
                depth -= 1
                if len(arrays) == 0:
                    return current
                done = current
                current = outer.pop()
                array = arrays[-1]
                if array:
                    current.append(done)
                else:
                    current[keys[-1]] = done
                keys.pop()
            more = p.deep_next(array)


def _array(p: _Parser, depth: int) -> list[Any]:
    out: list[Any] = []
    if p.begin(True):
        return out
    while True:
        out.append(_value(p, depth + 1))
        if not p.next_item(True):
            return out


def _object(p: _Parser, depth: int) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if p.begin(False):
        return out
    while True:
        key = p.object_key()
        out[key] = _value(p, depth + 1)
        if not p.next_item(False):
            return out


def _parse(p: _Parser) -> Any:
    p.start_document()
    value = _value(p, 0)
    p.end_document()
    return value


def loads(s: str) -> Any:
    """Decode JSON text into Any values: its arrays are list[Any], its objects dict[str, Any]."""
    try:
        return _parse(_Parser(s, False))
    except UnicodeDecodeError:
        return _parse(_Parser(s, True))


def load(fp: TextIO) -> Any:
    """Decode the JSON text that fp.read() returns into Any values, as loads() does."""
    return loads(fp.read())


def _floatstr(value: float, allow_nan: bool) -> str:
    if value != value or value == float("inf") or value == -float("inf"):
        if not allow_nan:
            raise ValueError("Out of range float values are not JSON compliant: " + repr(value))
        return "NaN" if value != value else "Infinity" if value > 0.0 else "-Infinity"
    return repr(value)


class _Writer:
    def __init__(self, skipkeys: bool, ensure_ascii: bool, check_circular: bool, allow_nan: bool,
                 sort_keys: bool, item_separator: str, key_separator: str, default: Any,
                 pretty: bool, indent: str, one_shot: bool) -> None:
        self.pretty = pretty  # (an indent was given: each item goes on its own line)
        self.indent = indent
        # dumps() nests as CPython's C encoder does, whatever the recursion limit: 9,998 containers
        # and default() conversions in progress, of which the first 64 are calls of write() and
        # the deeper ones deep()'s. dump() is CPython's Python encoder: a call for each, which
        # the recursion limit bounds.
        self.calls_free = 64 if one_shot else 20000
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
        self.chain = 0  # (default() calls in progress, each converting the value the one before returned)
        self.open: list[Any] = []  # (the containers being written, for check_circular)
        # (what separates the items of each dict being written, and what precedes its first)
        self.separators: list[str] = []
        self.inners: list[str] = []

    def enter(self, value: Any, depth: int) -> None:
        if self.circular:
            for parent in self.open:
                if value is parent:
                    raise ValueError("Circular reference detected")
        if depth >= 2000:  # (dump()'s bound: calls for each container, within the native stack)
            raise RecursionError("maximum recursion depth exceeded while encoding a JSON object")
        self.open.append(value)

    def supported_key(self, k: Any) -> bool:
        return k is None or isinstance(k, (str, int, float))

    def skips(self, k: Any) -> bool:
        # does skipkeys skip key k, which no JSON key spells
        return self.skipkeys and not self.supported_key(k)

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
            if depth + self.chain >= self.calls_free:
                self.deep(value, depth)
                return
            self.enter(value, depth)
            out.append("[")
            separator = self.item_separator
            lines = self.pretty and len(value) > 0
            if lines:
                # (CPython writes an empty container on one line, with or without an indent)
                inner = "\n" + self.indent * (depth + 1)
                separator += inner
                out.append(inner)
            first = True
            for item in value:
                if not first:
                    out.append(separator)
                first = False
                self.write(item, depth + 1)
            if lines:
                out.append("\n" + self.indent * depth)
            out.append("]")
            self.open.pop()
        elif isinstance(value, dict):
            if depth + self.chain >= self.calls_free:
                self.deep(value, depth)
                return
            self.enter(value, depth)
            out.append("{")
            # (as CPython's: the first line break comes with the first key written, so a dict
            # whose every key skipkeys skips is written as an empty one)
            self.separators.append(self.item_separator)
            self.inners.append("")
            if self.pretty:
                self.inners[-1] = "\n" + self.indent * (depth + 1)
                self.separators[-1] += self.inners[-1]
            first = True
            if self.sort_keys:
                # (CPython sorts a list of the items first: a default() callback's change to a
                # value is not seen)
                for k, v in sorted(value.items()):
                    if self.entry(k, v, first, depth):
                        first = False
            else:
                # Read values when their queued keys are reached, skip deleted keys, and append
                # newly observed keys after callbacks. This differs from CPython's live table
                # cursor for delete/reinsert and clear/repopulate: output order or entries can
                # differ (tests/deviations/dynany_json_reinsert.py). Without callbacks the dict
                # is unchanged.
                # A key skipkeys skips is not looked up or hashed again: it writes nothing either way
                keys = list(value)
                calls = self.calls
                i = 0
                while i < len(keys):
                    k = keys[i]
                    i += 1
                    if not self.skips(k):
                        if not self.supported_key(k):
                            # Reject an unsupported key without hashing it again. After a callback,
                            # it may have been deleted: check its identity in the live keys first.
                            present = self.calls == calls
                            if not present:
                                for live in value:
                                    if live is k:
                                        present = True
                                        break
                            if present:
                                self.key(k)
                        elif (self.calls == calls or k in value) and self.entry(k, value[k], first, depth):
                            first = False
                    if i == len(keys) and self.calls != calls:
                        # Deleted unsupported keys must not be hashed while looking for additions
                        # either. Any live unsupported key is still to reject (or skip).
                        seen = {x: True for x in keys if self.supported_key(x)}
                        keys.extend([x for x in value if not self.skips(x) and (not self.supported_key(x) or x not in seen)])
            self.separators.pop()
            self.inners.pop()
            if self.pretty and not first:
                out.append("\n" + self.indent * depth)
            out.append("}")
            self.open.pop()
        elif self.default is not None:
            # a chain of default() calls, each converting the value the one before returned, in a
            # loop: each value is checked for a circular reference and held until the chain's last
            # is written. The chain is bounded as CPython 3.13's C recursion limit on Linux bounds
            # its encoder, whose call of default() is the one that raises: 9,997 conversions in
            # progress and containers around them
            n = len(self.open)
            while True:
                self.enter(value, 0)
                self.calls += 1
                self.chain += 1
                if self.chain + depth > (9997 if self.calls_free == 64 else 10000):
                    raise RecursionError("maximum recursion depth exceeded")
                value = self.default(value)
                if value is None or isinstance(value, (str, int, float, list, tuple, dict)):
                    break
            self.write(value, depth)
            self.chain -= len(self.open) - n
            while len(self.open) > n:
                self.open.pop()
        else:
            raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")

    def deep(self, value: Any, depth: int) -> None:
        # The container at depth and all that it holds, as write() and entry() write them, with
        # the open containers and default() conversions on lists where those have them in their
        # calls: nesting then counts against neither the recursion limit nor the native stack,
        # and stops where CPython's C encoder does, at 9,998 containers and conversions in
        # progress. That encoder counts a container before it looks for a circular reference,
        # and so does this.
        out = self.out
        circular = self.circular
        pretty = self.pretty
        opened: set[int] = set()
        if circular:
            for parent in self.open:
                opened.add(id(parent))
        # each open container (0 a list or tuple, 1 a dict, 2 a dict in sorted order), or 3: a
        # chain of default() conversions, whose last value is written above it
        kinds: list[int] = []
        values: list[Any] = []  # (the container)
        at: list[int] = []  # (the next item's or key's index, or the number of a chain's conversions)
        # of each open dict:
        keys: list[list[Any]] = []  # (its keys, or each sorted key and then its value)
        calls: list[int] = []  # (default() calls when it was opened: after one, it may have changed)
        wrote: list[bool] = []  # (it wrote an entry)
        held: list[Any] = []  # (the values that chains converted)
        while True:
            if isinstance(value, list) or isinstance(value, tuple) or isinstance(value, dict):
                if depth + self.chain >= 9998:
                    raise RecursionError("maximum recursion depth exceeded while encoding a JSON object")
                if circular:
                    if id(value) in opened:
                        raise ValueError("Circular reference detected")
                    opened.add(id(value))
                depth += 1
                values.append(value)
                at.append(0)
                if pretty:
                    # (as write(): what precedes a container's first item, and what separates two)
                    self.inners.append("\n" + self.indent * depth)
                    self.separators.append(self.item_separator + self.inners[-1])
                if isinstance(value, dict):
                    out.append("{")
                    wrote.append(False)
                    calls.append(self.calls)
                    if self.sort_keys:
                        kinds.append(2)
                        pairs: list[Any] = []
                        for k, v in sorted(value.items()):
                            pairs.append(k)
                            pairs.append(v)
                        keys.append(pairs)
                    else:
                        kinds.append(1)
                        keys.append(list(value))
                else:
                    out.append("[")
                    kinds.append(0)
                    if pretty and len(value) > 0:
                        out.append(self.inners[-1])
            elif value is None:
                # (a scalar, as write() writes it: a call of write() here would make the two one
                # recursion)
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
            elif self.default is not None:
                # (a chain of default() calls, as write()'s)
                n = 0
                while True:
                    if circular:
                        if id(value) in opened:
                            raise ValueError("Circular reference detected")
                        opened.add(id(value))
                    held.append(value)
                    n += 1
                    self.calls += 1
                    self.chain += 1
                    if self.chain + depth > 9997:
                        raise RecursionError("maximum recursion depth exceeded")
                    value = self.default(value)
                    if value is None or isinstance(value, (str, int, float, list, tuple, dict)):
                        break
                kinds.append(3)
                values.append(None)
                at.append(n)
                continue
            else:
                raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")
            # the next value to write: the next item of the innermost open container that has
            # one, after closing those that have none
            while True:
                if len(kinds) == 0:
                    return
                kind = kinds[-1]
                i = at[-1]
                if kind == 0:
                    items = values[-1]
                    if i < len(items):
                        if i > 0:
                            out.append(self.separators[-1] if pretty else self.item_separator)
                        at[-1] = i + 1
                        value = items[i]
                        break
                    # (a list that had an item when it was opened has its items on their own lines)
                    if pretty and i > 0:
                        out.append("\n" + self.indent * (depth - 1))
                    out.append("]")
                elif kind == 3:
                    # (the chain's last value is written: its conversions are over)
                    self.chain -= i
                    while i > 0:
                        if circular:
                            opened.discard(id(held[-1]))
                        held.pop()
                        i -= 1
                else:
                    found = False
                    names = keys[-1]
                    if kind == 2:
                        while i < len(names):
                            k = names[i]
                            i += 2
                            if not self.skips(k):
                                value = names[i - 1]
                                found = True
                                break
                    else:
                        # (write()'s walk of a dict that default() calls may change)
                        container = values[-1]
                        while True:
                            if i == len(names):
                                if i > 0 and self.calls != calls[-1]:
                                    seen = {x: True for x in names if self.supported_key(x)}
                                    names.extend([x for x in container if not self.skips(x) and (not self.supported_key(x) or x not in seen)])
                                if i == len(names):
                                    break
                            k = names[i]
                            i += 1
                            if not self.skips(k):
                                if not self.supported_key(k):
                                    present = self.calls == calls[-1]
                                    if not present:
                                        for live in container:
                                            if live is k:
                                                present = True
                                                break
                                    if present:
                                        self.key(k)
                                elif self.calls == calls[-1] or k in container:
                                    value = container[k]
                                    found = True
                                    break
                    at[-1] = i
                    if found:
                        # (entry(), but for its call of write())
                        s = self.key(k)
                        if wrote[-1]:
                            out.append(self.separators[-1] if pretty else self.item_separator)
                        elif pretty:
                            out.append(self.inners[-1])
                        wrote[-1] = True
                        _quote(out, s, self.ascii)
                        out.append(self.key_separator)
                        break
                    if pretty and wrote[-1]:
                        out.append("\n" + self.indent * (depth - 1))
                    out.append("}")
                    keys.pop()
                    calls.pop()
                    wrote.pop()
                if kind != 3:
                    if circular:
                        opened.discard(id(values[-1]))
                    if pretty:
                        self.inners.pop()
                        self.separators.pop()
                    depth -= 1
                kinds.pop()
                values.pop()
                at.pop()

    def entry(self, k: Any, v: Any, first: bool, depth: int) -> bool:
        # writes k: v of a dict, after an item separator unless first; False where skipkeys
        # skips k, which writes nothing
        out = self.out
        if self.skips(k):
            return False
        s = self.key(k)
        if not first:
            out.append(self.separators[-1])
        elif self.pretty:
            out.append(self.inners[-1])
        _quote(out, s, self.ascii)
        out.append(self.key_separator)
        self.write(v, depth + 1)
        return True


def _indent_text(indent: Any) -> str:
    # one level of dumps()'s indent: the str itself, or that many spaces (none for 0 or less),
    # as CPython makes it, ' ' * indent (json's own takes a JSONValue: this module's values
    # do not cross into it)
    if indent is None:
        return ""
    if isinstance(indent, str):
        return indent
    if isinstance(indent, int):
        return " " * indent
    raise TypeError(f"can't multiply sequence by non-int of type '{type(indent).__name__}'")


def dumps(obj: Any, *, skipkeys: bool = False, ensure_ascii: bool = True, check_circular: bool = True,
          allow_nan: bool = True, indent: Any = None, separators: tuple[str, str] | None = None,
          default: Any = None, sort_keys: bool = False) -> str:
    """Encode Any values, as CPython's json.dumps() without cls."""
    item_separator = ", " if indent is None else ","  # (an indented line ends without a space)
    key_separator = ": "
    if separators is not None:
        item_separator = separators[0]
        key_separator = separators[1]
    w = _Writer(skipkeys, ensure_ascii, check_circular, allow_nan, sort_keys, item_separator, key_separator, default,
                indent is not None, _indent_text(indent), True)
    w.write(obj, 0)
    return "".join(w.out)


def dump(obj: Any, fp: TextIO, *, skipkeys: bool = False, ensure_ascii: bool = True, check_circular: bool = True,
         allow_nan: bool = True, indent: Any = None, separators: tuple[str, str] | None = None,
         default: Any = None, sort_keys: bool = False) -> None:
    """Write the text dumps() returns to fp (one write, where CPython writes it in pieces)."""
    item_separator = ", " if indent is None else ","
    key_separator = ": "
    if separators is not None:
        item_separator = separators[0]
        key_separator = separators[1]
    w = _Writer(skipkeys, ensure_ascii, check_circular, allow_nan, sort_keys, item_separator, key_separator, default,
                indent is not None, _indent_text(indent), False)
    w.write(obj, 0)
    fp.write("".join(w.out))


def _raw_decode(s: str, idx: int = 0) -> tuple[Any, int]:
    try:
        return _raw_parse(_Parser(s, False), idx)
    except UnicodeDecodeError:
        return _raw_parse(_Parser(s, True), idx)


def _raw_parse(p: _Parser, idx: int) -> tuple[Any, int]:
    p.seek_char(idx)
    value = _value(p, 0)
    return value, p.char_index(p.pos)
