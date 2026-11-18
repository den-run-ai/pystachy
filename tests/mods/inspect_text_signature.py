# A consumer of inspect that does not opt in to dynamic Any, after mypyc/ir/func_ir.py's
# get_text_signature() (mypy 2.4.1): a module-level dict from an enum's members to parameter
# kinds, parameters made with defaults of several types, appended to a list that a Signature
# takes, and the signature formatted in an f-string. mypyc's "default: object" holds the marker
# and then other values, which one variable cannot here: each call passes its own default.
import enum
import inspect
from typing import Final


class ArgKind(enum.Enum):
    ARG_POS = 0
    ARG_OPT = 1
    ARG_STAR = 2
    ARG_NAMED = 3
    ARG_STAR2 = 4
    ARG_NAMED_OPT = 5


_ARG_KIND_TO_INSPECT: Final = {
    ArgKind.ARG_POS: inspect.Parameter.POSITIONAL_OR_KEYWORD,
    ArgKind.ARG_OPT: inspect.Parameter.POSITIONAL_OR_KEYWORD,
    ArgKind.ARG_STAR: inspect.Parameter.VAR_POSITIONAL,
    ArgKind.ARG_NAMED: inspect.Parameter.KEYWORD_ONLY,
    ArgKind.ARG_STAR2: inspect.Parameter.VAR_KEYWORD,
    ArgKind.ARG_NAMED_OPT: inspect.Parameter.KEYWORD_ONLY,
}


class RuntimeArg:
    def __init__(self, name: str, kind: ArgKind, pos_only: bool = False) -> None:
        self.name = name
        self.kind = kind
        self.pos_only = pos_only

    @property
    def optional(self) -> bool:
        return self.kind == ArgKind.ARG_OPT or self.kind == ArgKind.ARG_NAMED_OPT


def get_text_signature(fn_name: str, args: list[RuntimeArg],
                       defaults: dict[str, int | float | str | bool | None],
                       pairs: dict[str, tuple[int, str]], *, bound: bool = False) -> str | None:
    """Return a text signature in CPython's internal doc format, or None
    if the function's signature cannot be represented.
    """
    parameters = []
    mark_self = not bound
    # Pre-scan for end of positional-only parameters.
    pos_only_idx = -1
    for idx, arg in enumerate(args):
        if arg.pos_only and arg.kind in (ArgKind.ARG_POS, ArgKind.ARG_OPT):
            pos_only_idx = idx
    for idx, arg in enumerate(args):
        if arg.name.startswith(("__bitmap", "__mypyc")):
            continue
        kind = (
            inspect.Parameter.POSITIONAL_ONLY
            if idx <= pos_only_idx
            else _ARG_KIND_TO_INSPECT[arg.kind]
        )
        if not arg.optional:
            curr_param = inspect.Parameter(arg.name, kind)
        elif arg.name in pairs:
            curr_param = inspect.Parameter(arg.name, kind, default=pairs[arg.name])
        elif arg.name in defaults:
            curr_param = inspect.Parameter(arg.name, kind, default=defaults[arg.name])
        else:
            # This default argument cannot be represented in a __text_signature__
            return None
        parameters.append(curr_param)
        if mark_self:
            # Parameter.__init__/Parameter.replace do not accept $
            curr_param._name = f"${arg.name}"
            mark_self = False
    return f"{fn_name}{inspect.Signature(parameters)}"


def kind_names(args: list[RuntimeArg]) -> list[str]:
    return [str(_ARG_KIND_TO_INSPECT[arg.kind]) for arg in args]


def count_keyword_only(parameters: list[inspect.Parameter]) -> int:
    return len([p for p in parameters if p.kind == inspect.Parameter.KEYWORD_ONLY])


def without_default(parameters: list[inspect.Parameter]) -> list[str]:
    return [p.name for p in parameters if p.default is inspect.Parameter.empty]
