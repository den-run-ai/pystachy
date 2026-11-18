"""Blocker taxonomy for first compiler errors, and the language/library split of CPython test files.

Categories (first error only; imports come first in a file, so missing modules mask later blockers):
  library   - a stdlib module, name or builtin API that is not provided yet (porting work)
  syntax    - a statement, expression or parameter form that is not implemented yet
  typing    - static typing friction: inference needs an annotation, or a value's type differs from
              the single static type chosen for it (monomorphic typing)
  dynamic   - semantics outside the static object model: classes/modules/functions as runtime
              values, classes in functions, builtin/multiple/generic bases, dynamic class bodies,
              eval/exec/compile, frame/exception/GC introspection and reflective modules
  other     - anything else
"""
import re

REFLECTIVE_MODULES = {"gc", "inspect", "dis", "ast", "marshal", "pickle", "copyreg", "pydoc", "symtable",
                      "code", "codeop", "importlib", "tracemalloc"}

RULES = [
    # dynamic: needs a runtime that can create, inspect or evaluate program structure
    ("dynamic", r"unsupported call (eval|exec|compile)\("),
    ("dynamic", r"a class inside a function is not supported"),
    ("dynamic", r"unsupported base class|single inheritance requires|only an exception class may have a base"),
    ("dynamic", r"inheritance with generic class templates"),
    ("dynamic", r"multiple inheritance"),
    ("dynamic", r"a class body may only contain"),
    ("dynamic", r"cannot be used as a value"),
    ("dynamic", r"str\.format\(\) of a format string computed at run time"),
    ("dynamic", r"attributes of an exception"),
    ("dynamic", r"namedtuple\(\) is only supported as"),
    ("dynamic", r"statements are only supported at a module's top level"),
    ("dynamic", r"nonlocal '[^']*' is not supported here"),
    ("dynamic", r"distinct function types|function attribute|metaclass|__class__|__dict__|__slots__"),
    ("dynamic", r"unsupported call typing\.TypeVar|TypeVar '[^']*'"),
    ("dynamic", r"unsupported call (getattr|setattr|delattr|hasattr|type|vars|globals|locals|super)\("),
    ("dynamic", r"classes are not values|class objects|a class as a value|first-class class"),
    ("dynamic", r"a class statement inside a block"),
    ("dynamic", r"redefinition of '|its body holds statements|of an enum class is not supported"),
    # static representation restrictions (typed containers, fixed-width ints, identity) count as typing
    ("typing", r"elements must be|keys must be|'is' is only supported for|isinstance\(\) is only supported with"),
    ("typing", r"does not fit in 64 bits|cannot compare .* != |without a return annotation|must derive from BaseException"),
    ("typing", r"^expected .*, got "),
    ("syntax", r"\*\*kwargs is not supported|empty tuples are not supported|invalid target for augmented assignment"),
    ("library", r"is only supported in a for loop|map\(\) is not supported|\.sort\(key=\.\.\.\)|takes exactly|takes no arguments"),
    ("library", r"takes \d+ to \d+ arguments|does not accept keyword|called as a function is not supported"),
    # syntax / not-yet-implemented language features
    ("syntax", r"statements are not supported|'yield' is not supported|'await' is not supported|'except\*' is not supported"),
    ("syntax", r"'nonlocal' is not supported|'global' is not supported|lambda is not supported"),
    ("syntax", r"literals are not supported|comprehensions are not supported|star arguments|\*args, \*\*kwargs"),
    ("syntax", r"parameter markers|keyword-only|positional-only|default (argument|value)s? (is|are) not supported"),
    ("syntax", r"unsupported decorator|decorators? (is|are) not supported"),
    ("syntax", r"nested functions and classes are not supported|class inheritance is not supported"),
    ("syntax", r"slice steps|'for \.\.\. else'|'while \.\.\. else'|assignment expressions|asynchronous comprehensions"),
    ("syntax", r"non-ASCII identifiers|complex numbers are not supported|'__file__' is not supported"),
    ("syntax", r"conditional (expression|import)|chained comparison|f-strings?|format spec|'del' is not supported|'assert'"),
    ("syntax", r"^expected '.*' but found|^unexpected '|unterminated|invalid syntax|tabs in indentation|\\N\{"),
    ("syntax", r"generator expressions? (is|are) not supported|'with' is not supported|'async'|'match'"),
    ("syntax", r"an except clause needs exception classes|is not supported in a (class|function) body"),
    # library: modules, names and APIs not provided yet
    ("library", r"module '([^']*)' is not supported|No module named|no module named"),
    ("library", r"cannot import name|from '[^']*' is not supported: no definition"),
    ("library", r"module '[^']*' has no attribute|unsupported module attribute"),
    ("library", r"has no method|unexpected keyword argument|keyword argument '[^']*' of [a-z_.]+\(\) is not supported"),
    ("library", r"types\.[A-Za-z]+ is not supported|unsupported call|is not supported by Pystachy|not implemented"),
    # typing friction
    ("typing", r"cannot infer|needs a type annotation|annotate it|add a type annotation|does not bind its type variable"),
    ("typing", r"^expected [^,]+, got |incompatible|type mismatch|cannot assign|unsupported operand type"),
    ("typing", r"object has no attribute|is not an iterator|is not callable|is not subscriptable|not iterable"),
    ("typing", r"different types|distinct types|union|Optional|None has no|may be None|takes \d+ positional"),
]


def strip(detail):
    d = re.sub(r"^[^ ]*?\.py: (error: )?", "", detail or "")
    return re.sub(r"\(available: [^)]*\)", "(available: ...)", d)


def category(detail):
    d = strip(detail)
    m = re.search(r"module '([^']*)' is not supported", d)
    if m and m.group(1).split(".")[0] in REFLECTIVE_MODULES:
        return "dynamic"
    for cat, pattern in RULES:
        if re.search(pattern, d):
            return cat
    return "other"


LANGUAGE_FILES = {
    "augassign", "baseexception", "binop", "bool", "builtin", "bytes", "call", "class", "compare", "contains",
    "coroutines", "decorators", "dict", "dictcomps", "dictviews", "enumerate", "exception_variations",
    "exceptions", "extcall", "float", "format", "fstring", "generators", "global", "grammar", "hash", "int",
    "int_literal", "isinstance", "iter", "keywordonlyarg", "list", "listcomps", "long", "named_expressions",
    "opcodes", "patma", "positional_only_arg", "pow", "print", "property", "raise", "range", "richcmp", "scope",
    "set", "setcomps", "slice", "sort", "str", "string_literals", "super", "tuple", "type_aliases",
    "type_params", "types", "unary", "unpack", "unpack_ex", "with",
}


def group(file):
    name = file.replace("Lib/test/", "").replace(".py", "")
    return "language" if name.replace("test_", "", 1) in LANGUAGE_FILES else "library"
