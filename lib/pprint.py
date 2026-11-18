#  Author:      Fred L. Drake, Jr.
#               fdrake@acm.org
#
#  This is a simple little module I wrote to make life easier.  I didn't
#  see anything quite like it in the library, though I may have overlooked
#  something.  I wrote this when I was trying to read some heavily nested
#  tuples with fairly non-descriptive content.  This is modeled very much
#  after Lisp/Scheme - style pretty-printing of lists.  If you find it
#  useful, thank small children who sleep at night.

"""Support to pretty-print lists, tuples, & dictionaries recursively.

Very simple, but useful, especially in debugging data structures.

Classes
-------

PrettyPrinter()
    Handle pretty-printing operations onto a stream using a configured
    set of formatting parameters.

Functions
---------

pformat()
    Format a Python object into a pretty-printed representation.

pprint()
    Pretty-print a Python object to a stream [default is sys.stdout].

saferepr()
    Generate a 'standard' repr()-like value, but protect against recursive
    data structures.

"""

# Pystachy port of CPython 3.13.16's Lib/pprint.py (lib/provenance.md); each adaptation is marked
# "Pystachy port". CPython's PrettyPrinter looks type(object).__repr__ up in a table of its
# methods. A compiled program has no class objects as values, so the static type of each value
# selects its method here: isinstance() of a type that rules the value's out is decided as the
# program compiles, as in lib/copy.py. Dicts, lists, tuples, sets, frozensets, strs and bytes are
# wrapped as CPython wraps them, at any nesting; every other value is written as its repr()
# (lib/compatibility.md#pprint).

# Pystachy port: no collections, dataclasses, re or types. Their classes are written as their
# repr(), and _split_spaces() below is the one regex.
import sys as _sys
from io import StringIO as _StringIO

__all__ = ["pprint","pformat","isreadable","isrecursive","saferepr",
           "PrettyPrinter", "pp"]


# Pystachy port: the options are annotated here and below (CPython converts indent and width with
# int() and takes any object for the flags); object and stream take their arguments' types.
def pprint(object, stream=None, indent: int = 1, width: int = 80, depth: int | None = None, *,
           compact: bool = False, sort_dicts: bool = True, underscore_numbers: bool = False) -> None:
    """Pretty-print a Python object to a stream [default is sys.stdout]."""
    printer = PrettyPrinter(
        stream=stream, indent=indent, width=width, depth=depth,
        compact=compact, sort_dicts=sort_dicts,
        underscore_numbers=underscore_numbers)
    printer.pprint(object)

def pformat(object, indent: int = 1, width: int = 80, depth: int | None = None, *,
            compact: bool = False, sort_dicts: bool = True, underscore_numbers: bool = False) -> str:
    """Format a Python object into a pretty-printed representation."""
    return PrettyPrinter(indent=indent, width=width, depth=depth,
                         compact=compact, sort_dicts=sort_dicts,
                         underscore_numbers=underscore_numbers).pformat(object)

# Pystachy port: pprint()'s parameters written out (CPython: *args and **kwargs, passed on).
def pp(object, stream=None, indent: int = 1, width: int = 80, depth: int | None = None, *,
       compact: bool = False, sort_dicts: bool = False, underscore_numbers: bool = False) -> None:
    """Pretty-print a Python object"""
    pprint(object, stream, indent, width, depth, compact=compact, sort_dicts=sort_dicts,
           underscore_numbers=underscore_numbers)

def saferepr(object) -> str:
    """Version of repr() which can handle recursive data structures."""
    return PrettyPrinter()._safe_repr(object, {}, None, 0)[0]

def isreadable(object) -> bool:
    """Determine if saferepr(object) is readable by eval()."""
    return PrettyPrinter()._safe_repr(object, {}, None, 0)[1]

def isrecursive(object) -> bool:
    """Determine if object requires a recursive representation."""
    return PrettyPrinter()._safe_repr(object, {}, None, 0)[2]

class _safe_key:
    """Helper function for key functions when sorting unorderable objects.

    The wrapped-object will fallback to a Py2.x style comparison for
    unorderable types (sorting first comparing the type name and then by
    the obj ids).  Does not work recursively, so dict.items() must have
    _safe_key applied to both the key and the value.

    """

    __slots__ = ['obj']

    def __init__(self, obj) -> None:
        self.obj = obj

    def __lt__(self, other) -> bool:
        try:
            return self.obj < other.obj
        except TypeError:
            # Pystachy port: in no order (CPython: by the pairs (str(type(x)), id(x)); there is
            # no id(), and the two values have one static type). The < of two objects of a class
            # that defines no __lt__() raises nothing: it does not compile.
            return False

def _safe_item(o):
    # Pystachy port: _safe_key as a function, for sorted()'s key
    return _safe_key(o)

def _safe_tuple(t):
    "Helper function for comparing 2-tuples"
    # Pystachy port: the key's _safe_key alone. CPython's pair (_safe_key(t[0]), _safe_key(t[1]))
    # compares as its first item does, a _safe_key being equal to itself only.
    return _safe_key(t[0])

# Pystachy port: _format_items()'s locals between two items, which _format_item() reads and writes.
class _Items:
    def __init__(self, indent: int, allowance: int, width: int) -> None:
        self.indent = indent
        self.allowance = allowance
        self.delimnl = ',\n' + ' ' * indent
        self.delim = ''
        self.width = width
        self.max_width = width

# Pystachy port: a class template, as stream takes its argument's type; no class derives from one.
class PrettyPrinter:
    def __init__(self, indent: int = 1, width: int = 80, depth: int | None = None, stream=None, *,
                 compact: bool = False, sort_dicts: bool = True, underscore_numbers: bool = False) -> None:
        """Handle pretty printing operations onto a stream using a set of
        configured parameters.

        indent
            Number of spaces to indent for each level of nesting.

        width
            Attempted maximum number of columns in the output.

        depth
            The maximum depth to print out nested structures.

        stream
            The desired output stream.  If omitted (or false), the standard
            output stream available at construction will be used.

        compact
            If true, several items will be combined in one line.

        sort_dicts
            If true, dict keys are sorted.

        underscore_numbers
            If true, digit groups are separated with underscores.

        """
        # Pystachy port: no int(indent), int(width) or bool(compact) (the annotations)
        if indent < 0:
            raise ValueError('indent must be >= 0')
        if depth is not None and depth <= 0:
            raise ValueError('depth must be > 0')
        if not width:
            raise ValueError('width must be != 0')
        self._depth = depth
        self._indent_per_level = indent
        self._width = width
        # Pystachy port: the stream given, where None stands for sys.stdout, which pprint() reads
        # (CPython stores sys.stdout here; a field has one type, and a file is not optional)
        self._stream = stream
        self._compact = compact
        self._sort_dicts = sort_dicts
        self._underscore_numbers = underscore_numbers

    def pprint(self, object) -> None:
        # Pystachy port: _pprint_to() tests the stream, as its parameter (see __init__)
        self._pprint_to(object, self._stream)

    def _pprint_to(self, object, stream) -> None:
        # Pystachy port: pprint()'s body, on sys.stdout for no stream
        if stream is None:
            self._format(object, _sys.stdout, 0, 0, {}, 0)
            _sys.stdout.write("\n")
        else:
            self._format(object, stream, 0, 0, {}, 0)
            stream.write("\n")

    def pformat(self, object) -> str:
        sio = _StringIO()
        self._format(object, sio, 0, 0, {}, 0)
        return sio.getvalue()

    def isrecursive(self, object) -> bool:
        return self.format(object, {}, 0, 0)[2]

    def isreadable(self, object) -> bool:
        s, readable, recursive = self.format(object, {}, 0, 0)
        return readable and not recursive

    # Pystachy port: context, CPython's dict of the id() of each container being written, stays
    # empty: there is no id(). A value of a static type holds itself only through an object of
    # a class, which is written as its repr(), or as a list or dict of a recursive value alias,
    # which the recursion limit stops. So no object is found again in context, _recursion() is
    # not here and nothing is found recursive.
    def _format(self, object, stream, indent: int, allowance: int, context: dict[int, int], level: int) -> None:
        rep = self._repr(object, context, level)
        max_width = self._width - indent - allowance
        if len(rep) > max_width:
            # Pystachy port: the method of object's static type (CPython: _dispatch's method for
            # type(object).__repr__, and _pprint_dataclass(); see the head of this file)
            if isinstance(object, dict):
                self._pprint_dict(object, stream, indent, allowance, context, level + 1)
                return
            if isinstance(object, list):
                self._pprint_list(object, stream, indent, allowance, context, level + 1)
                return
            if isinstance(object, tuple):
                # Pystachy port: a tuple, but no NamedTuple, whose __repr__ is its class's:
                # type(object) is tested as the program runs
                if type(object) is tuple:
                    self._pprint_tuple(object, stream, indent, allowance, context, level + 1)
                    return
            if isinstance(object, (set, frozenset)):
                self._pprint_set(object, stream, indent, allowance, context, level + 1)
                return
            if isinstance(object, bytes):
                self._pprint_bytes(object, stream, indent, allowance, context, level + 1)
                return
            # Pystachy port: a str by type(object), tested as the program runs, and str(object),
            # the same str (isinstance() of a StrEnum member and str does not compile)
            if type(object) is str:
                self._pprint_str(str(object), stream, indent, allowance, context, level + 1)
                return
        stream.write(rep)

    def _pprint_dict(self, object, stream, indent: int, allowance: int, context: dict[int, int], level: int) -> None:
        write = stream.write
        write('{')
        if self._indent_per_level > 1:
            write((self._indent_per_level - 1) * ' ')
        length = len(object)
        if length:
            # Pystachy port: one call for each kind of items (a sorted list, or the dict's view)
            if self._sort_dicts:
                self._format_dict_items(sorted(object.items(), key=_safe_tuple), stream, indent,
                                        allowance + 1, context, level)
            else:
                self._format_dict_items(object.items(), stream, indent, allowance + 1,
                                        context, level)
        write('}')

    def _pprint_list(self, object, stream, indent: int, allowance: int, context: dict[int, int], level: int) -> None:
        stream.write('[')
        self._format_items(object, stream, indent, allowance + 1,
                           context, level)
        stream.write(']')

    def _pprint_tuple(self, object, stream, indent: int, allowance: int, context: dict[int, int], level: int) -> None:
        stream.write('(')
        endchar = ',)' if len(object) == 1 else ')'
        # Pystachy port: _format_tuple_items(), which is _format_items() of a tuple
        self._format_tuple_items(object, stream, indent, allowance + len(endchar),
                                 context, level)
        stream.write(endchar)

    def _pprint_set(self, object, stream, indent: int, allowance: int, context: dict[int, int], level: int) -> None:
        if not len(object):
            stream.write(repr(object))
            return
        # Pystachy port: a set or a frozenset (CPython: object.__class__, and its name)
        if isinstance(object, set):
            stream.write('{')
            endchar = '}'
        else:
            stream.write('frozenset({')
            endchar = '})'
            indent += len('frozenset') + 1
        # Pystachy port: key=_safe_item, a function (a class is no value)
        self._format_items(sorted(object, key=_safe_item), stream, indent, allowance + len(endchar),
                           context, level)
        stream.write(endchar)

    def _pprint_str(self, object: str, stream, indent: int, allowance: int, context: dict[int, int], level: int) -> None:
        write = stream.write
        if not len(object):
            write(repr(object))
            return
        chunks: list[str] = []
        lines = object.splitlines(True)
        if level == 1:
            indent += 1
            allowance += 1
        max_width1 = max_width = self._width - indent
        rep = ''  # Pystachy port: bound before the loop, which runs (object is not empty)
        for i, line in enumerate(lines):
            rep = repr(line)
            if i == len(lines) - 1:
                max_width1 -= allowance
            if len(rep) <= max_width1:
                chunks.append(rep)
            else:
                # A list of alternating (non-space, space) strings
                # Pystachy port: re.findall(r'\S*\s*', line) without its empty last part
                parts = _split_spaces(line)
                max_width2 = max_width
                current = ''
                for j, part in enumerate(parts):
                    candidate = current + part
                    if j == len(parts) - 1 and i == len(lines) - 1:
                        max_width2 -= allowance
                    if len(repr(candidate)) > max_width2:
                        if current:
                            chunks.append(repr(current))
                        current = part
                    else:
                        current = candidate
                if current:
                    chunks.append(repr(current))
        if len(chunks) == 1:
            write(rep)
            return
        if level == 1:
            write('(')
        for i, rep in enumerate(chunks):
            if i > 0:
                write('\n' + ' '*indent)
            write(rep)
        if level == 1:
            write(')')

    def _pprint_bytes(self, object: bytes, stream, indent: int, allowance: int, context: dict[int, int], level: int) -> None:
        write = stream.write
        if len(object) <= 4:
            write(repr(object))
            return
        parens = level == 1
        if parens:
            indent += 1
            allowance += 1
            write('(')
        delim = ''
        for rep in _wrap_bytes_repr(object, self._width - indent, allowance):
            write(delim)
            write(rep)
            if not delim:
                delim = '\n' + ' '*indent
        if parens:
            write(')')

    def _format_dict_items(self, items, stream, indent: int, allowance: int, context: dict[int, int],
                           level: int) -> None:
        write = stream.write
        indent += self._indent_per_level
        delimnl = ',\n' + ' ' * indent
        last_index = len(items) - 1
        for i, (key, ent) in enumerate(items):
            last = i == last_index
            rep = self._repr(key, context, level)
            write(rep)
            write(': ')
            self._format(ent, stream, indent + len(rep) + 2,
                         allowance if last else 1,
                         context, level)
            if not last:
                write(delimnl)

    # Pystachy port: _format_items()'s loop has its locals in an _Items, which _begin_items()
    # makes after CPython's first lines, and its body in _format_item(). _format_each() steps
    # through the items as CPython does; a tuple's are _format_tuple_items()'s.
    def _format_items(self, items, stream, indent: int, allowance: int, context: dict[int, int], level: int) -> None:
        st = self._begin_items(stream, indent, allowance)
        self._format_each(items, st, stream, context, level)

    def _begin_items(self, stream, indent: int, allowance: int) -> _Items:
        write = stream.write
        indent += self._indent_per_level
        if self._indent_per_level > 1:
            write((self._indent_per_level - 1) * ' ')
        return _Items(indent, allowance, self._width - indent + 1)

    def _format_tuple_items(self, items, stream, indent: int, allowance: int, context: dict[int, int], level: int) -> None:
        # Pystachy port: _format_items() of a tuple, whose items may have types of their own: a
        # tuple of up to nine has one call for each, on a slice of one item (no item is read
        # past the end of a shorter tuple). Nine are as many as a tuple of such items has where
        # it has a repr(); longer tuples, whose items have one type, are stepped through. more
        # is empty unless there are more than nine: its length is known as the program
        # compiles, as that of a NamedTuple is not (its type reaches here, though no NamedTuple
        # does).
        st = self._begin_items(stream, indent, allowance)
        more = items[9:10]
        if len(more) == 0:
            n = len(items)
            self._format_one(items[0:1], n == 1, st, stream, context, level)
            self._format_one(items[1:2], n == 2, st, stream, context, level)
            self._format_one(items[2:3], n == 3, st, stream, context, level)
            self._format_one(items[3:4], n == 4, st, stream, context, level)
            self._format_one(items[4:5], n == 5, st, stream, context, level)
            self._format_one(items[5:6], n == 6, st, stream, context, level)
            self._format_one(items[6:7], n == 7, st, stream, context, level)
            self._format_one(items[7:8], n == 8, st, stream, context, level)
            self._format_one(items[8:9], n == 9, st, stream, context, level)
        else:
            self._format_each(items, st, stream, context, level)

    def _format_one(self, one, last: bool, st: _Items, stream, context: dict[int, int], level: int) -> None:
        # Pystachy port: _format_item() of the item of a tuple's slice, if it has one
        if len(one) == 1:
            self._format_item(one[0], last, st, stream, context, level)

    def _format_each(self, items, st: _Items, stream, context: dict[int, int], level: int) -> None:
        it = iter(items)
        try:
            next_ent = next(it)
        except StopIteration:
            return
        last = False
        while not last:
            ent = next_ent
            try:
                next_ent = next(it)
            except StopIteration:
                last = True
            self._format_item(ent, last, st, stream, context, level)

    def _format_item(self, ent, last: bool, st: _Items, stream, context: dict[int, int], level: int) -> None:
        write = stream.write
        if last:
            st.max_width -= st.allowance
            st.width -= st.allowance
        if self._compact:
            rep = self._repr(ent, context, level)
            w = len(rep) + 2
            if st.width < w:
                st.width = st.max_width
                if st.delim:
                    st.delim = st.delimnl
            if st.width >= w:
                st.width -= w
                write(st.delim)
                st.delim = ', '
                write(rep)
                return
        write(st.delim)
        st.delim = st.delimnl
        self._format(ent, stream, st.indent,
                     st.allowance if last else 1,
                     context, level)

    def _repr(self, object, context: dict[int, int], level: int) -> str:
        # Pystachy port: no self._readable or self._recursive, which nothing reads
        rep, readable, recursive = self.format(object, context.copy(),
                                               self._depth, level)
        return rep

    def format(self, object, context: dict[int, int], maxlevels: int | None, level: int) -> tuple[str, bool, bool]:
        """Format object for a specific context, returning a string
        and flags indicating whether the representation is 'readable'
        and whether the object represents a recursive construct.
        """
        return self._safe_repr(object, context, maxlevels, level)

    def _safe_repr(self, object, context: dict[int, int], maxlevels: int | None, level: int) -> tuple[str, bool, bool]:
        # Return triple (repr_string, isreadable, isrecursive).
        # Pystachy port: object's static type, where CPython reads type(object) and its __repr__.
        # The scalars (CPython's _builtin_scalars, and an int) need no test here: the last
        # return finds their repr() readable, and groups an int's digits before it.
        if isinstance(object, dict):
            if not object:
                return "{}", True, False
            if maxlevels and level >= maxlevels:
                return "{...}", False, False
            readable = True
            components: list[str] = []
            level += 1
            # Pystachy port: one loop for each kind of items, whose body is _safe_repr_pair()
            if self._sort_dicts:
                for k, v in sorted(object.items(), key=_safe_tuple):
                    if not self._safe_repr_pair(k, v, components, context, maxlevels, level):
                        readable = False
            else:
                for k, v in object.items():
                    if not self._safe_repr_pair(k, v, components, context, maxlevels, level):
                        readable = False
            return "{%s}" % ", ".join(components), readable, False

        if isinstance(object, list):
            if not object:
                return "[]", True, False
            if maxlevels and level >= maxlevels:
                return "[...]", False, False
            readable = True
            components: list[str] = []
            level += 1
            for o in object:
                if not self._safe_repr_item(o, components, context, maxlevels, level):
                    readable = False
            return "[%s]" % ", ".join(components), readable, False

        if isinstance(object, tuple):
            # Pystachy port: a tuple, but no NamedTuple (see _format()); _safe_repr_tuple() is
            # CPython's code for it
            if type(object) is tuple:
                return self._safe_repr_tuple(object, context, maxlevels, level)

        # Pystachy port: the rest is _safe_repr_other(), which reads object as its parameter,
        # whatever the tests above have left of a union
        return self._safe_repr_other(object)

    def _safe_repr_other(self, object) -> tuple[str, bool, bool]:
        rep = repr(object)
        # Pystachy port: an int's digits in groups, from its repr() (CPython: f"{object:_d}", for
        # an int whose __repr__ is int's; isinstance() of an IntEnum member and int does not
        # compile, and type(object) is tested as the program runs)
        if self._underscore_numbers and type(object) is int:
            return _underscored(rep), True, False
        # Pystachy port: a bool (CPython gives rep itself where it is empty)
        return rep, (len(rep) > 0 and not rep.startswith('<')), False

    def _safe_repr_tuple(self, object, context: dict[int, int], maxlevels: int | None, level: int) -> tuple[str, bool, bool]:
        # Pystachy port: end closes the repr (CPython: a format, "(%s,)" or "(%s)", for %)
        if len(object) == 1:
            end = ",)"
        else:
            if not object:
                return "()", True, False
            end = ")"
        if maxlevels and level >= maxlevels:
            return "(..." + end, False, False
        components: list[str] = []
        level += 1
        # Pystachy port: one call for each item of a tuple of up to nine, as
        # _format_tuple_items()
        readable = True
        more = object[9:10]
        if len(more) == 0:
            if not self._safe_repr_one(object[0:1], components, context, maxlevels, level):
                readable = False
            if not self._safe_repr_one(object[1:2], components, context, maxlevels, level):
                readable = False
            if not self._safe_repr_one(object[2:3], components, context, maxlevels, level):
                readable = False
            if not self._safe_repr_one(object[3:4], components, context, maxlevels, level):
                readable = False
            if not self._safe_repr_one(object[4:5], components, context, maxlevels, level):
                readable = False
            if not self._safe_repr_one(object[5:6], components, context, maxlevels, level):
                readable = False
            if not self._safe_repr_one(object[6:7], components, context, maxlevels, level):
                readable = False
            if not self._safe_repr_one(object[7:8], components, context, maxlevels, level):
                readable = False
            if not self._safe_repr_one(object[8:9], components, context, maxlevels, level):
                readable = False
        else:
            for o in object:
                if not self._safe_repr_item(o, components, context, maxlevels, level):
                    readable = False
        return "(" + ", ".join(components) + end, readable, False

    def _safe_repr_pair(self, k, v, components: list[str], context: dict[int, int], maxlevels: int | None, level: int) -> bool:
        # Pystachy port: _safe_repr() of a dict's key and value: their part of its repr, appended
        # to components; whether both are readable
        krepr, kreadable, krecur = self.format(
            k, context, maxlevels, level)
        vrepr, vreadable, vrecur = self.format(
            v, context, maxlevels, level)
        components.append("%s: %s" % (krepr, vrepr))
        return kreadable and vreadable

    def _safe_repr_item(self, o, components: list[str], context: dict[int, int], maxlevels: int | None, level: int) -> bool:
        # Pystachy port: _safe_repr() of a list's or a tuple's item, as _safe_repr_pair()
        orepr, oreadable, orecur = self.format(
            o, context, maxlevels, level)
        components.append(orepr)
        return oreadable

    def _safe_repr_one(self, one, components: list[str], context: dict[int, int], maxlevels: int | None, level: int) -> bool:
        # Pystachy port: _safe_repr_item() of the item of a tuple's slice, if it has one
        if len(one) == 1:
            return self._safe_repr_item(one[0], components, context, maxlevels, level)
        return True

def _underscored(rep: str) -> str:
    # Pystachy port: f"{n:_d}" from repr(n): the digits in groups of three, after the sign
    sign = ''
    if rep.startswith('-'):
        sign = '-'
        rep = rep[1:]
    groups: list[str] = []
    end = len(rep)
    while end > 3:
        groups.append(rep[end - 3:end])
        end -= 3
    groups.append(rep[:end])
    groups.reverse()
    return sign + '_'.join(groups)

def _split_spaces(line: str) -> list[str]:
    # Pystachy port: the parts re.findall(r'\S*\s*', line) gives before its empty last one: each
    # run of characters that are not spaces with the spaces that follow it
    parts: list[str] = []
    part: list[str] = []
    spaces = False
    for ch in line:
        if ch.isspace():
            spaces = True
        elif spaces:
            parts.append(''.join(part))
            part = []
            spaces = False
        part.append(ch)
    if part:
        parts.append(''.join(part))
    return parts

def _wrap_bytes_repr(object: bytes, width: int, allowance: int):
    current = b''
    last = len(object) // 4 * 4
    for i in range(0, len(object), 4):
        part = object[i: i+4]
        candidate = current + part
        if i == last:
            width -= allowance
        if len(repr(candidate)) > width:
            if current:
                yield repr(current)
            current = part
        else:
            current = candidate
    if current:
        yield repr(current)
