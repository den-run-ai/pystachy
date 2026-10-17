from __future__ import annotations

from collections.abc import Mapping
# Pystachy port: no datetime and types modules (#11): no date and time values, and
# COMPACT_ESCAPES is a dict instead of a MappingProxyType

TYPE_CHECKING = False
if TYPE_CHECKING:
    from collections.abc import Generator
    from decimal import Decimal
    from typing import IO, Any, Final

ASCII_CTRL = frozenset(chr(i) for i in range(32)) | frozenset(chr(127))
ILLEGAL_BASIC_STR_CHARS = frozenset('"\\') | ASCII_CTRL - frozenset("\t")
BARE_KEY_CHARS = frozenset(
    "abcdefghijklmnopqrstuvwxyz" "ABCDEFGHIJKLMNOPQRSTUVWXYZ" "0123456789" "-_"
)
# Pystachy port: no ARRAY_TYPES = (list, tuple): classes are not values (M2)
MAX_LINE_LENGTH = 100

COMPACT_ESCAPES = (  # Pystachy port: was MappingProxyType(
    {
        "\u0008": "\\b",  # backspace
        "\u000A": "\\n",  # linefeed
        "\u000C": "\\f",  # form feed
        "\u000D": "\\r",  # carriage return
        "\u0022": '\\"',  # quote
        "\u005C": "\\\\",  # backslash
    }
)


class Context:
    def __init__(self, allow_multiline: bool, indent: int):
        if indent < 0:
            raise ValueError("Indent width must be non-negative")
        self.allow_multiline: Final = allow_multiline
        # cache rendered inline tables (mapping from object id to rendered inline table)
        self.inline_table_cache: Final[dict[int, str]] = {}
        self.indent_str: Final = " " * indent


def dump(
    obj: Mapping[str, Any],
    fp: IO[bytes],
    /,
    *,
    multiline_strings: bool = False,
    indent: int = 4,
) -> None:
    ctx = Context(multiline_strings, indent)
    for chunk in gen_table_chunks(obj, ctx, name=""):
        fp.write(chunk.encode())


def dumps(
    obj: Mapping[str, Any], /, *, multiline_strings: bool = False, indent: int = 4
) -> str:
    ctx = Context(multiline_strings, indent)
    return "".join(gen_table_chunks(obj, ctx, name=""))


# Pystachy port: returns the list of the chunks instead of being a generator (M7): each
# `yield` is chunks.append(), and `yield from` chunks.extend()
def gen_table_chunks(
    table: Mapping[str, Any],
    ctx: Context,
    *,
    name: str,
    inside_aot: bool = False,
) -> list[str]:  # Pystachy port: was Generator[str, None, None]
    chunks: list[str] = []
    yielded = False
    # Pystachy port: literals and tables hold keys, and the loops below look the values up.
    # Where all the values of a type of document are tables, or none are, one of the lists
    # stays empty, and Pystachy cannot type an empty list of pairs of a key and any value (M4).
    literals: list[str] = []
    tables: list[str] = []  # => [key of a table or an array of tables]
    for k, v in table.items():
        if isinstance(v, Mapping):
            tables.append(k)  # Pystachy port: was tables.append((k, v, False))
        # Pystachy port: is_aot()'s tests of the types also made on names, which Pystachy
        # decides at compile time, so that it compiles is_suitable_inline_table() for
        # tables only (M4)
        elif (
            isinstance(v, (list, tuple))
            and is_aot(v)
            and not all(isinstance(t, Mapping) and is_suitable_inline_table(t, ctx) for t in v)
        ):
            tables.append(k)  # Pystachy port: was tables.extend((k, t, True) for t in v)
        else:
            literals.append(k)  # Pystachy port: was literals.append((k, v))

    if inside_aot or name and (literals or not tables):
        yielded = True
        chunks.append(f"[[{name}]]\n" if inside_aot else f"[{name}]\n")  # Pystachy port: was yield

    if literals:
        yielded = True
        for k in literals:  # Pystachy port: was `for k, v in literals:`
            chunks.append(f"{format_key_part(k)} = {format_literal(table[k], ctx)}\n")

    # Pystachy port: the key of a table, or of an array of tables, whose tables are written
    # inside_aot: upstream looped over (key, table, inside_aot) triples
    for k in tables:
        v = table[k]
        if isinstance(v, Mapping):
            if yielded:
                chunks.append("\n")
            else:
                yielded = True
            key_part = format_key_part(k)
            display_name = f"{name}.{key_part}" if name else key_part
            chunks.extend(gen_table_chunks(v, ctx, name=display_name, inside_aot=False))
        elif isinstance(v, (list, tuple)):
            for t in v:
                if isinstance(t, Mapping):
                    if yielded:
                        chunks.append("\n")
                    else:
                        yielded = True
                    key_part = format_key_part(k)
                    display_name = f"{name}.{key_part}" if name else key_part
                    chunks.extend(gen_table_chunks(t, ctx, name=display_name, inside_aot=True))
    return chunks


# Pystachy port: the parameters annotated object, Mapping or `tuple | list`, here and below, are
# not annotated (M1): these functions are templates, compiled for each type of document, where a
# value of any type would need M4
def format_literal(obj, ctx: Context, *, nest_level: int = 0) -> str:  # Pystachy port: obj: object
    if isinstance(obj, bool):
        return "true" if obj else "false"
    # Pystachy port: no date, datetime and time values (#11)
    if isinstance(obj, (int, float)):
        return str(obj)
    if isinstance(obj, str):
        return format_string(obj, allow_multiline=ctx.allow_multiline)
    if isinstance(obj, (list, tuple)):  # Pystachy port: was ARRAY_TYPES
        return format_inline_array(obj, ctx, nest_level)
    if isinstance(obj, Mapping):
        return format_inline_table(obj, ctx)

    # Lazy import to improve module import time
    from decimal import Decimal

    if isinstance(obj, Decimal):
        return format_decimal(obj)
    raise TypeError(
        f"Object of type '{type(obj).__qualname__}' is not TOML serializable"
    )


def format_decimal(obj: Decimal) -> str:
    if obj.is_nan():
        return "nan"
    if obj.is_infinite():
        return "-inf" if obj.is_signed() else "inf"
    dec_str = str(obj).lower()
    return dec_str if "." in dec_str or "e" in dec_str else dec_str + ".0"


def format_inline_table(obj, ctx: Context) -> str:  # Pystachy port: obj: Mapping
    # Pystachy port: no cache keyed by id(obj) (M4): a table is rendered each time
    if not obj:
        rendered = "{}"
    else:
        rendered = (
            "{ "
            + ", ".join(
                f"{format_key_part(k)} = {format_literal(v, ctx)}"
                for k, v in obj.items()
            )
            + " }"
        )
    return rendered


# Pystachy port: obj: tuple | list
def format_inline_array(obj, ctx: Context, nest_level: int) -> str:
    if not obj:
        return "[]"
    item_indent = ctx.indent_str * (1 + nest_level)
    closing_bracket_indent = ctx.indent_str * nest_level
    return (
        "[\n"
        + ",\n".join(
            item_indent + format_literal(item, ctx, nest_level=nest_level + 1)
            for item in obj
        )
        + f",\n{closing_bracket_indent}]"
    )


def format_key_part(part: str) -> str:
    # Pystachy port: no try for the TypeError of a key that is no str (M2: its message names
    # type(part), and type() of a str is no value); part is a str
    only_bare_key_chars = BARE_KEY_CHARS.issuperset(part)

    if part and only_bare_key_chars:
        return part
    return format_string(part, allow_multiline=False)


def format_string(s: str, *, allow_multiline: bool) -> str:
    do_multiline = allow_multiline and "\n" in s
    if do_multiline:
        result = '"""\n'
        s = s.replace("\r\n", "\n")
    else:
        result = '"'

    pos = seq_start = 0
    while True:
        try:
            char = s[pos]
        except IndexError:
            result += s[seq_start:pos]
            if do_multiline:
                return result + '"""'
            return result + '"'
        if char in ILLEGAL_BASIC_STR_CHARS:
            result += s[seq_start:pos]
            if char in COMPACT_ESCAPES:
                if do_multiline and char == "\n":
                    result += "\n"
                else:
                    result += COMPACT_ESCAPES[char]
            else:
                result += "\\u" + hex(ord(char))[2:].rjust(4, "0")
            seq_start = pos + 1
        pos += 1


def is_aot(obj: Any) -> bool:
    """Decides if an object behaves as an array of tables (i.e. a nonempty list
    of dicts)."""
    return bool(
        isinstance(obj, (list, tuple))  # Pystachy port: was ARRAY_TYPES
        and bool(obj)  # Pystachy port: was obj: the operands of `and` have one type (M4)
        and all(isinstance(v, Mapping) for v in obj)
    )


def is_suitable_inline_table(obj, ctx: Context) -> bool:  # Pystachy port: obj: Mapping
    """Use heuristics to decide if the inline-style representation is a good
    choice for a given table."""
    rendered_inline = f"{ctx.indent_str}{format_inline_table(obj, ctx)},"
    return len(rendered_inline) <= MAX_LINE_LENGTH and "\n" not in rendered_inline
