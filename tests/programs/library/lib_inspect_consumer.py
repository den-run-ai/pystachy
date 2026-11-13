# inspect from modules that do not opt in to dynamic Any, in the shapes of mypyc/ir/func_ir.py
# (tests/mods/inspect_text_signature.py): kinds as a dict's values, defaults of int, float, str,
# bool, None and tuple values, a list of parameters as a Signature in an f-string, and a
# parameter's default and kind tested against Parameter.empty and Parameter.KEYWORD_ONLY
import inspect
import sys

from mods.inspect_text_signature import (ArgKind, RuntimeArg, count_keyword_only, get_text_signature, kind_names,
                                         without_default)

n = len(sys.argv)  # 3: a number that only the run knows
args = [
    RuntimeArg("self", ArgKind.ARG_POS),
    RuntimeArg("a", ArgKind.ARG_POS),
    RuntimeArg("count", ArgKind.ARG_OPT),
    RuntimeArg("ratio", ArgKind.ARG_OPT),
    RuntimeArg("__bitmap", ArgKind.ARG_OPT),
    RuntimeArg("rest", ArgKind.ARG_STAR),
    RuntimeArg("key", ArgKind.ARG_NAMED),
    RuntimeArg("label", ArgKind.ARG_NAMED_OPT),
    RuntimeArg("flag", ArgKind.ARG_NAMED_OPT),
    RuntimeArg("missing", ArgKind.ARG_NAMED_OPT),
    RuntimeArg("pair", ArgKind.ARG_NAMED_OPT),
    RuntimeArg("options", ArgKind.ARG_STAR2),
]
defaults: dict[str, int | float | str | bool | None] = {
    "count": n * 14, "ratio": n / 2, "label": "x" * n, "flag": n == 3, "missing": None}
pairs = {"pair": (n, "three")}
print(get_text_signature("method", args, defaults, pairs))
print(get_text_signature("function", args[1:], defaults, pairs, bound=True))
print(get_text_signature("empty", [], defaults, pairs))
print(get_text_signature("pos_only", [RuntimeArg("x", ArgKind.ARG_POS, True), RuntimeArg("y", ArgKind.ARG_OPT, True),
                                      RuntimeArg("z", ArgKind.ARG_OPT)], {"y": 1, "z": 2}, pairs, bound=True))
print(get_text_signature("unrepresentable", [RuntimeArg("q", ArgKind.ARG_OPT)], defaults, pairs))
print(kind_names(args))

parameters = [
    inspect.Parameter("a", inspect.Parameter.POSITIONAL_OR_KEYWORD),
    inspect.Parameter("b", inspect.Parameter.POSITIONAL_OR_KEYWORD, default=n),
    inspect.Parameter("c", inspect.Parameter.KEYWORD_ONLY, default=None),
    inspect.Parameter("d", inspect.Parameter.KEYWORD_ONLY),
]
print(count_keyword_only(parameters), without_default(parameters))
for p in parameters:
    print(p.name, p.default is inspect.Parameter.empty, p.default is not inspect.Parameter.empty,
          p.kind == inspect.Parameter.KEYWORD_ONLY, p.kind != inspect.Parameter.KEYWORD_ONLY, str(p.kind), p.kind,
          f"{p}|{p.kind}|{p.default}")
print(f"f{inspect.Signature(parameters)}", "f" + str(inspect.Signature(parameters)))
