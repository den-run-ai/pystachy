# pystachy: dynamic-any
"""Get useful information from live Python objects.

This module encapsulates the interface provided by the internal special
attributes (co_*, tb_*, etc.) in a friendlier fashion.
It also provides some help for examining source code and class layout.

Here are some of the useful functions provided by this module:

    ismodule(), isclass(), ismethod(), isfunction(), isgeneratorfunction(),
        isgenerator(), istraceback(), isframe(), iscode(), isbuiltin(),
        isroutine() - check object types
    getmembers() - get members of an object that satisfy a given condition

    getfile(), getsourcefile(), getsource() - find an object's source code
    getdoc(), getcomments() - get documentation on an object
    getmodule() - determine the module that an object came from
    getclasstree() - arrange classes so as to represent their hierarchy

    getargvalues(), getcallargs() - get info about function arguments
    getfullargspec() - same, with support for Python 3 features
    formatargvalues() - format an argument spec
    getouterframes(), getinnerframes() - get info about frames
    currentframe() - get the current stack frame
    stack(), trace() - get info about frames on the stack or in a traceback

    signature() - get a Signature object for the callable

    get_annotations() - safely compute an object's annotations
"""

# Pystachy's subset of CPython 3.13.16's Lib/inspect.py (lib/provenance.md,
# lib/compatibility.md#inspect): Parameter and Signature as objects that a program makes itself,
# their kinds, the empty marker, formatannotation() and cleandoc(), with CPython's code, docstrings
# and comments where it compiles; each change is marked "Pystachy port". What the docstring above
# lists is not provided: a compiled program has no code objects, frames, class dictionaries or
# source files for signature(), getmembers(), isfunction() and the others to ask, and a name this
# module lacks is a compile-time error. The module opts in to dynamic Any (comment above) for a
# parameter's default and annotation and a signature's return annotation, which are values of
# whatever types the caller gives (docs/dynamic-any-boundaries.md).

# This module is in the public domain.  No warranties.

__author__ = ('Ka-Ping Yee <ping@lfw.org>',
              'Yury Selivanov <yselivanov@sprymix.com>')

# Pystachy port: of CPython's names, those this subset has
__all__ = [
    "Parameter",
    "Signature",
    "cleandoc",
    "formatannotation",
]


# Pystachy port: of CPython's imports, those this subset uses
import enum
import sys
import types
from keyword import iskeyword
from typing import Any  # Pystachy port: (defaults and annotations are Any values)


def cleandoc(doc: str) -> str:
    """Clean up indentation from docstrings.

    Any whitespace that can be uniformly removed from the second line
    onwards is removed."""
    lines = doc.expandtabs().split('\n')

    # Find minimum indentation of any non-blank lines after first line.
    margin = sys.maxsize
    for line in lines[1:]:
        content = len(line.lstrip(' '))
        if content:
            indent = len(line) - content
            margin = min(margin, indent)
    # Remove indentation.
    if lines:
        lines[0] = lines[0].lstrip(' ')
    if margin < sys.maxsize:
        for i in range(1, len(lines)):
            lines[i] = lines[i][margin:]
    # Remove any trailing or leading blank lines.
    while lines and not lines[-1]:
        lines.pop()
    while lines and not lines[0]:
        lines.pop(0)
    return '\n'.join(lines)


# Pystachy port: str.isidentifier() is not supported. The characters of ASCII that start an
# identifier and go on with it are the letters, the digits and "_"; of the others, which Unicode's
# XID_Start and XID_Continue tables decide, this module has no tables (re's are not imported: the
# regex engine would then track the identity of its numbers in every program that imports
# inspect, as the modules that a module compiled with dynamic Any imports do). A name that only
# those characters could make an identifier is therefore an explicit error
def _isidentifier(name: str) -> bool:
    other = False
    for i in range(len(name)):
        c = name[i]
        if not c.isascii():
            other = True
        elif not (c == '_' or 'a' <= c <= 'z' or 'A' <= c <= 'Z' or (i > 0 and '0' <= c <= '9')):
            return False
    if other:
        raise NotImplementedError("inspect: a parameter name with characters outside ASCII "
                                  "is not supported: " + repr(name))
    return len(name) > 0


# Pystachy port: annotation is an Any value. A typing form or a generic alias (list[int]) is no
# value here, so CPython's two branches for them are left out
def formatannotation(annotation: Any, base_module: str | None = None) -> str:
    if isinstance(annotation, type):
        if annotation.__module__ in ('builtins', base_module):
            return annotation.__qualname__
        return annotation.__module__+'.'+annotation.__qualname__
    # Pystachy port: an enum class as a value is an object of enum's EnumType here, which does
    # not know its module (in CPython it is a class, which the branch above formats)
    if type(annotation).__name__ == 'EnumType' and type(annotation).__module__ == 'enum':
        raise NotImplementedError("inspect: an enum class as an annotation is not supported")
    return repr(annotation)


# Pystachy port: CPython's _void and _empty are classes, used as values. A class is no value
# here, so each is the one object of a private class: _empty, which is also Parameter.empty and
# Signature.empty, has the repr() of CPython's class, and "is" tells it from every other value.
class _VoidType:
    """A private marker - used in Parameter & Signature."""

    def __repr__(self) -> str:
        return "<class 'inspect._void'>"


class _EmptyType:
    """Marker object for Signature.empty and Parameter.empty."""

    def __repr__(self) -> str:
        return "<class 'inspect._empty'>"


_void = _VoidType()
_empty = _EmptyType()


# Pystachy port: CPython's members are made by __new__ from their descriptions, numbered as they
# are defined; an enum class takes no __new__ here, so the members have those numbers as their
# values and description is a property
_DESCRIPTIONS = ('positional-only', 'positional or keyword', 'variadic positional',
                 'keyword-only', 'variadic keyword')


class _ParameterKind(enum.IntEnum):
    POSITIONAL_ONLY = 0
    POSITIONAL_OR_KEYWORD = 1
    VAR_POSITIONAL = 2
    KEYWORD_ONLY = 3
    VAR_KEYWORD = 4

    @property
    def description(self) -> str:
        return _DESCRIPTIONS[self.value]

    def __str__(self) -> str:
        return self.name

_POSITIONAL_ONLY         = _ParameterKind.POSITIONAL_ONLY
_POSITIONAL_OR_KEYWORD   = _ParameterKind.POSITIONAL_OR_KEYWORD
_VAR_POSITIONAL          = _ParameterKind.VAR_POSITIONAL
_KEYWORD_ONLY            = _ParameterKind.KEYWORD_ONLY
_VAR_KEYWORD             = _ParameterKind.VAR_KEYWORD


class Parameter:
    """Represents a parameter in a function signature.

    Has the following public attributes:

    * name : str
        The name of the parameter as a string.
    * default : object
        The default value for the parameter if specified.  If the
        parameter has no default value, this attribute is set to
        `Parameter.empty`.
    * annotation
        The annotation for the parameter if specified.  If the
        parameter has no annotation, this attribute is set to
        `Parameter.empty`.
    * kind
        Describes how argument values are bound to the parameter.
        Possible values: `Parameter.POSITIONAL_ONLY`,
        `Parameter.POSITIONAL_OR_KEYWORD`, `Parameter.VAR_POSITIONAL`,
        `Parameter.KEYWORD_ONLY`, `Parameter.VAR_KEYWORD`.
        Every value has a `description` attribute describing meaning.
    """

    __slots__ = ('_name', '_kind', '_default', '_annotation')

    POSITIONAL_ONLY         = _ParameterKind.POSITIONAL_ONLY
    POSITIONAL_OR_KEYWORD   = _ParameterKind.POSITIONAL_OR_KEYWORD
    VAR_POSITIONAL          = _ParameterKind.VAR_POSITIONAL
    KEYWORD_ONLY            = _ParameterKind.KEYWORD_ONLY
    VAR_KEYWORD             = _ParameterKind.VAR_KEYWORD

    empty: _EmptyType = _empty

    def __init__(self, name: Any, kind: _ParameterKind, *, default: Any = _empty,
                 annotation: Any = _empty) -> None:
        # Pystachy port: kind is a member (an int is a compile-time error), or None, as an object
        # of a class may be, where CPython looks the member up: _ParameterKind(kind)
        if kind is None:
            raise ValueError('value None is not a valid Parameter.kind')
        self._kind = kind
        if default is not _empty:
            if self._kind in (_VAR_POSITIONAL, _VAR_KEYWORD):
                # Pystachy port: one expression (str.format() takes a literal format string)
                msg = '{} parameters cannot have default values'.format(
                    self._kind.description)
                raise ValueError(msg)
        self._default: Any = default
        self._annotation: Any = annotation

        if name is _empty:
            raise ValueError('name is a required attribute for Parameter')

        if not isinstance(name, str):
            msg = 'name must be a str, not a {}'.format(type(name).__name__)
            raise TypeError(msg)

        # Pystachy port: the name as a str variable, after the test above (name is an Any value,
        # for CPython's errors of a name that is no str)
        text: str = name
        if text[0] == '.' and text[1:].isdigit():
            # These are implicit arguments generated by comprehensions. In
            # order to provide a friendlier interface to users, we recast
            # their name as "implicitN" and treat them as positional-only.
            # See issue 19611.
            if self._kind != _POSITIONAL_OR_KEYWORD:
                # Pystachy port: one expression (see above)
                msg = (
                    'implicit arguments must be passed as '
                    'positional or keyword arguments, not {}'
                ).format(self._kind.description)
                raise ValueError(msg)
            self._kind = _POSITIONAL_ONLY
            text = 'implicit{}'.format(text[1:])

        # It's possible for C functions to have a positional-only parameter
        # where the name is a keyword, so for compatibility we'll allow it.
        is_keyword = iskeyword(text) and self._kind is not _POSITIONAL_ONLY
        if is_keyword or not _isidentifier(text):
            raise ValueError('{!r} is not a valid parameter name'.format(text))

        self._name: str = text

    @property
    def name(self) -> str:
        return self._name

    @property
    def default(self) -> Any:
        return self._default

    @property
    def annotation(self) -> Any:
        return self._annotation

    @property
    def kind(self) -> _ParameterKind:
        return self._kind

    def replace(self, *, name: Any = _void, kind: _ParameterKind | _VoidType = _void,
                annotation: Any = _void, default: Any = _void) -> "Parameter":
        """Creates a customized copy of the Parameter."""

        if name is _void:
            name = self._name

        if kind is _void:
            kind = self._kind

        if annotation is _void:
            annotation = self._annotation

        if default is _void:
            default = self._default

        # Pystachy port: kind is a member or _void (or None, as an object of a class may be).
        # CPython calls type(self), a class as a value, whose call would take the kind as an Any
        # value, which a member cannot be: a Parameter's copy is made by name, and a subclass's
        # object has none
        if not isinstance(kind, _ParameterKind):
            raise ValueError('value None is not a valid Parameter.kind')
        if type(self) is not Parameter:
            raise NotImplementedError("inspect: replace() of an object of a subclass of "
                                      "Parameter is not supported")
        return Parameter(name, kind, default=default, annotation=annotation)

    def __str__(self) -> str:
        kind = self.kind
        formatted = self._name

        # Add annotation and default value
        if self._annotation is not _empty:
            formatted = '{}: {}'.format(formatted,
                                       formatannotation(self._annotation))

        if self._default is not _empty:
            if self._annotation is not _empty:
                formatted = '{} = {}'.format(formatted, repr(self._default))
            else:
                formatted = '{}={}'.format(formatted, repr(self._default))

        if kind == _VAR_POSITIONAL:
            formatted = '*' + formatted
        elif kind == _VAR_KEYWORD:
            formatted = '**' + formatted

        return formatted

    def __repr__(self) -> str:
        return '<{} "{}">'.format(self.__class__.__name__, self)

    def __hash__(self) -> int:
        # Pystachy port: the tuple of the four hashes (hash() takes no tuple that holds a kind or
        # an Any value)
        return hash((hash(self._name), hash(self._kind), hash(self._annotation),
                     hash(self._default)))

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True
        if not isinstance(other, Parameter):
            return False
        return (self._name == other._name and
                self._kind == other._kind and
                self._default == other._default and
                self._annotation == other._annotation)


# Pystachy port: a signature's parameters, a read-only view of a dict in their order (CPython's is
# of an OrderedDict). A function makes it, and not Signature.__init__ itself, whose class would
# be a class template if it called one (MappingProxyType is generic in its dict's types)
def _proxy(params: dict[str, Parameter]) -> types.MappingProxyType[str, Parameter]:
    return types.MappingProxyType(params)


# Pystachy port: Signature.replace()'s parameters when it is given none: a list of its own, which
# "is" tells from every list a caller passes, as CPython's _void is no value of a list's type
_VOID_PARAMETERS: list[Parameter] = []


class Signature:
    """A Signature object represents the overall signature of a function.
    It stores a Parameter object for each parameter accepted by the
    function, as well as information specific to the function itself.

    A Signature object has the following public attributes and methods:

    * parameters : OrderedDict
        An ordered mapping of parameters' names to the corresponding
        Parameter objects (keyword-only arguments are in the same order
        as listed in `code.co_varnames`).
    * return_annotation : object
        The annotation for the return type of the function if specified.
        If the function has no annotation for its return type, this
        attribute is set to `Signature.empty`.
    """

    __slots__ = ('_return_annotation', '_parameters')

    empty: _EmptyType = _empty

    def __init__(self, parameters: list[Parameter] | None = None, *,
                 return_annotation: Any = _empty,
                 __validate_parameters__: bool = True) -> None:
        """Constructs Signature from the given list of Parameter
        objects and 'return_annotation'.  All arguments are optional.
        """

        params: dict[str, Parameter] = {}
        if parameters is not None:
            if __validate_parameters__:
                top_kind = _POSITIONAL_ONLY
                seen_default = False

                for param in parameters:
                    kind = param.kind
                    name = param.name

                    if kind < top_kind:
                        msg = (
                            'wrong parameter order: {} parameter before {} '
                            'parameter'
                        ).format(top_kind.description,
                                 kind.description)
                        raise ValueError(msg)
                    elif kind > top_kind:
                        top_kind = kind

                    if kind in (_POSITIONAL_ONLY, _POSITIONAL_OR_KEYWORD):
                        if param.default is _empty:
                            if seen_default:
                                # No default for this parameter, but the
                                # previous parameter of had a default
                                msg = 'non-default argument follows default ' \
                                      'argument'
                                raise ValueError(msg)
                        else:
                            # There is a default for this parameter.
                            seen_default = True

                    if name in params:
                        msg = 'duplicate parameter name: {!r}'.format(name)
                        raise ValueError(msg)

                    params[name] = param
            else:
                for param in parameters:
                    params[param.name] = param

        self._parameters: types.MappingProxyType[str, Parameter] = _proxy(params)
        self._return_annotation: Any = return_annotation

    @property
    def parameters(self) -> types.MappingProxyType[str, Parameter]:
        return self._parameters

    @property
    def return_annotation(self) -> Any:
        return self._return_annotation

    def replace(self, *, parameters: list[Parameter] | None = _VOID_PARAMETERS,
                return_annotation: Any = _void) -> "Signature":
        """Creates a customized copy of the Signature.
        Pass 'parameters' and/or 'return_annotation' arguments
        to override them in the new copy.
        """

        if parameters is _VOID_PARAMETERS:
            parameters = list(self.parameters.values())

        if return_annotation is _void:
            return_annotation = self._return_annotation

        # Pystachy port: Signature by name, for CPython's type(self) (see Parameter.replace())
        if type(self) is not Signature:
            raise NotImplementedError("inspect: replace() of an object of a subclass of "
                                      "Signature is not supported")
        return Signature(parameters,
                         return_annotation=return_annotation)

    def _positional(self) -> list[Parameter]:
        return [param for param in self.parameters.values()
                      if param.kind != _KEYWORD_ONLY]

    def _keyword_only(self) -> dict[str, Parameter]:
        return {param.name: param for param in self.parameters.values()
                                  if param.kind == _KEYWORD_ONLY}

    def __hash__(self) -> int:
        h = hash(self._return_annotation)
        for param in self._positional():
            h = hash((h, hash(param)))
        kwo = 0
        for param in self._keyword_only().values():
            kwo ^= hash(param)
        return hash((h, kwo))

    def __eq__(self, other: object) -> bool:
        if self is other:
            return True
        if not isinstance(other, Signature):
            return False
        return (self._positional() == other._positional() and
                self._keyword_only() == other._keyword_only() and
                self._return_annotation == other._return_annotation)

    def __repr__(self) -> str:
        return '<{} {}>'.format(self.__class__.__name__, self)

    def __str__(self) -> str:
        return self.format()

    def format(self, *, max_width: int | None = None) -> str:
        """Create a string representation of the Signature object.

        If *max_width* integer is passed,
        signature will try to fit into the *max_width*.
        If signature is longer than *max_width*,
        all parameters will be on separate lines.
        """
        result: list[str] = []
        render_pos_only_separator = False
        render_kw_only_separator = True
        for param in self.parameters.values():
            formatted = str(param)

            kind = param.kind

            if kind == _POSITIONAL_ONLY:
                render_pos_only_separator = True
            elif render_pos_only_separator:
                # It's not a positional-only parameter, and the flag
                # is set to 'True' (there were pos-only params before.)
                result.append('/')
                render_pos_only_separator = False

            if kind == _VAR_POSITIONAL:
                # OK, we have an '*args'-like parameter, so we won't need
                # a '*' to separate keyword-only arguments
                render_kw_only_separator = False
            elif kind == _KEYWORD_ONLY and render_kw_only_separator:
                # We have a keyword-only parameter to render and we haven't
                # rendered an '*args'-like parameter before, so add a '*'
                # separator to the parameters list ("foo(arg1, *, arg2)" case)
                result.append('*')
                # This condition should be only triggered once, so
                # reset the flag
                render_kw_only_separator = False

            result.append(formatted)

        if render_pos_only_separator:
            # There were only positional-only parameters, hence the
            # flag was not reset to 'False'
            result.append('/')

        rendered = '({})'.format(', '.join(result))
        if max_width is not None and len(rendered) > max_width:
            rendered = '(\n    {}\n)'.format(',\n    '.join(result))

        if self.return_annotation is not _empty:
            anno = formatannotation(self.return_annotation)
            rendered += ' -> {}'.format(anno)

        return rendered
