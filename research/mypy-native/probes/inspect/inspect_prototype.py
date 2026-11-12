# pystachy: dynamic-any
import enum
from keyword import iskeyword
from typing import Any


class _void:
    """A private marker - used in Parameter & Signature."""


class _empty:
    """Marker object for Signature.empty and Parameter.empty."""


_DESCRIPTIONS = ('positional-only', 'positional or keyword', 'variadic positional', 'keyword-only',
                 'variadic keyword')


class _ParameterKind(enum.IntEnum):
    POSITIONAL_ONLY = 0
    POSITIONAL_OR_KEYWORD = 1
    VAR_POSITIONAL = 2
    KEYWORD_ONLY = 3
    VAR_KEYWORD = 4

    def __str__(self) -> str:
        return self.name


_POSITIONAL_ONLY = _ParameterKind.POSITIONAL_ONLY
_POSITIONAL_OR_KEYWORD = _ParameterKind.POSITIONAL_OR_KEYWORD
_VAR_POSITIONAL = _ParameterKind.VAR_POSITIONAL
_KEYWORD_ONLY = _ParameterKind.KEYWORD_ONLY
_VAR_KEYWORD = _ParameterKind.VAR_KEYWORD


class Parameter:
    POSITIONAL_ONLY: _ParameterKind = _ParameterKind.POSITIONAL_ONLY
    POSITIONAL_OR_KEYWORD: _ParameterKind = _ParameterKind.POSITIONAL_OR_KEYWORD
    VAR_POSITIONAL: _ParameterKind = _ParameterKind.VAR_POSITIONAL
    KEYWORD_ONLY: _ParameterKind = _ParameterKind.KEYWORD_ONLY
    VAR_KEYWORD: _ParameterKind = _ParameterKind.VAR_KEYWORD


    def __init__(self, name: str, kind: _ParameterKind, *, default: Any = _empty, annotation: Any = _empty) -> None:
        self._kind = kind
        if default is not _empty:
            if self._kind in (_VAR_POSITIONAL, _VAR_KEYWORD):
                msg = '{} parameters cannot have default values'
                msg = msg.format(_DESCRIPTIONS[self._kind.value])
                raise ValueError(msg)
        self._default: Any = default
        self._annotation: Any = annotation
        is_keyword = iskeyword(name) and self._kind is not _POSITIONAL_ONLY
        if is_keyword or not name.isidentifier():
            raise ValueError('{!r} is not a valid parameter name'.format(name))
        self._name = name

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

    def __str__(self) -> str:
        kind = self.kind
        formatted = self._name
        if self._annotation is not _empty:
            formatted = '{}: {}'.format(formatted, repr(self._annotation))
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
