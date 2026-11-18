"""The syntax tree: one node class for every kind of Ruff's ruff_python_ast nodes that the parser
builds, with generic fields whose meaning depends on the kind (see the table below).

Ranges are byte offsets into the parsed text (Ruff's TextRange).
"""

# expressions
E_BOOLOP = 1        # n: 0 and / 1 or; xs: values
E_NAMED = 2         # a: target; b: value
E_BINOP = 3         # a: left; n: operator (Ruff's Operator order); b: right
E_UNARYOP = 4       # n: 0 ~ / 1 not / 2 + / 3 -; a: operand
E_LAMBDA = 5        # a: parameters (P_PARAMETERS) or None; b: body
E_IF = 6            # a: body; b: test; c: orelse
E_DICT = 7          # xs: X_DICT_ITEM
E_SET = 8           # xs: elts
E_LISTCOMP = 9      # a: elt; xs: X_COMPREHENSION
E_SETCOMP = 10      # a: elt; xs: X_COMPREHENSION
E_DICTCOMP = 11     # a: key or None; b: value; xs: X_COMPREHENSION
E_GENERATOR = 12    # a: elt; xs: X_COMPREHENSION; flag: parenthesized
E_AWAIT = 13        # a: value
E_YIELD = 14        # a: value or None
E_YIELDFROM = 15    # a: value
E_COMPARE = 16      # a: left; ints: operators (0 == ... 9 not in); ys: comparators
E_CALL = 17         # a: func; b: X_ARGUMENTS
E_FSTRING = 18      # xs: parts (X_STRING_PART literals, X_FSTRING_PART)
E_TSTRING = 19      # xs: X_FSTRING_PART
E_STRING = 20       # xs: X_STRING_PART
E_BYTES = 21        # xs: X_BYTES_PART
E_INT = 22          # flag: fits i64 (ival), else s: Ruff's display (big); flag2: small (fits u64)
E_FLOAT = 23        # s: the value as struct packs a double (<d)
E_COMPLEX = 24      # s: the imaginary part, packed as E_FLOAT's
E_BOOL = 25         # flag: value
E_NONE = 26
E_ELLIPSIS = 27
E_ATTRIBUTE = 28    # a: value; s: attr; nstart/nend: attr range; n: ctx
E_SUBSCRIPT = 29    # a: value; b: slice; n: ctx
E_STARRED = 30      # a: value; n: ctx
E_NAME = 31         # s: id; n: ctx
E_LIST = 32         # xs: elts; n: ctx
E_TUPLE = 33        # xs: elts; n: ctx; flag: parenthesized
E_SLICE = 34        # a: lower; b: upper; c: step (each may be None)
E_IPY = 35

# statements
S_FUNCTIONDEF = 40  # s: name, nstart/nend; flag: async; xs: X_DECORATOR; a: P_PARAMETERS; b: returns; c: P_TYPE_PARAMS; ys: body
S_CLASSDEF = 41     # s: name, nstart/nend; xs: X_DECORATOR; a: X_ARGUMENTS or None; c: P_TYPE_PARAMS; ys: body
S_RETURN = 42       # a: value
S_DELETE = 43       # xs: targets
S_TYPEALIAS = 44    # a: name; c: P_TYPE_PARAMS; b: value
S_ASSIGN = 45       # xs: targets; a: value
S_AUGASSIGN = 46    # a: target; n: operator; b: value
S_ANNASSIGN = 47    # a: target; b: annotation; c: value; flag: simple
S_FOR = 48          # flag: async; a: target; b: iter; ys: body; zs: orelse
S_WHILE = 49        # a: test; ys: body; zs: orelse
S_IF = 50           # a: test; ys: body; xs: X_ELIF_ELSE
S_WITH = 51         # flag: async; xs: X_WITHITEM; ys: body
S_MATCH = 52        # a: subject; xs: X_MATCH_CASE
S_RAISE = 53        # a: exc; b: cause
S_TRY = 54          # ys: body; xs: X_EXCEPT_HANDLER; zs: orelse; c: X_BODY of the finalbody or None; flag: is_star
S_ASSERT = 55       # a: test; b: msg
S_IMPORT = 56       # xs: X_ALIAS; flag: lazy
S_IMPORTFROM = 57   # s: module, flag2: has module; xs: X_ALIAS; n: level; flag: lazy
S_GLOBAL = 58       # xs: X_IDENTIFIER
S_NONLOCAL = 59     # xs: X_IDENTIFIER
S_EXPR = 60         # a: value
S_PASS = 61
S_BREAK = 62
S_CONTINUE = 63
S_IPY = 64

# patterns
M_VALUE = 70        # a: value
M_SINGLETON = 71    # n: 0 None / 1 True / 2 False
M_SEQUENCE = 72     # xs: patterns
M_MAPPING = 73      # xs: keys; ys: patterns; flag: has rest, s: rest, nstart/nend
M_CLASS = 74        # a: cls; xs: patterns; ys: X_PATTERN_KEYWORD
M_STAR = 75         # flag: has name, s: name, nstart/nend
M_AS = 76           # a: pattern or None; flag: has name, s: name, nstart/nend
M_OR = 77           # xs: patterns

# other nodes
X_COMPREHENSION = 80  # a: target; b: iter; xs: ifs; flag: async
X_KEYWORD = 81        # flag: has arg, s: arg, nstart/nend; a: value
X_ARGUMENTS = 82      # xs: args; ys: X_KEYWORD
X_ALIAS = 83          # s: name, nstart/nend; flag: has asname, a: asname (X_IDENTIFIER), n/ival: asname range
X_WITHITEM = 84       # a: context expr; b: optional vars
X_EXCEPT_HANDLER = 85  # a: type; flag: has name, s: name, nstart/nend; ys: body
X_MATCH_CASE = 86     # a: pattern; b: guard; ys: body
X_ELIF_ELSE = 87      # a: test or None; ys: body
X_DECORATOR = 88      # a: expression
X_IDENTIFIER = 89     # s
X_DICT_ITEM = 90      # a: key or None; b: value
X_STRING_PART = 91    # s: value (UTF-8); n: token flags
X_BYTES_PART = 92     # s: value; n: token flags
X_FSTRING_PART = 93   # xs: elements (X_FS_LITERAL, X_FS_INTERP); n: flags
X_FS_LITERAL = 94     # s: value
X_FS_INTERP = 95      # a: expression; flag: debug text, s: the text before the expression (ival bytes) and after it; n: conversion (-1, 115 s, 114 r, 97 a); b: X_FORMAT_SPEC or None
X_FORMAT_SPEC = 96    # xs: elements
X_PATTERN_KEYWORD = 97  # s: attr, nstart/nend; a: pattern
X_BODY = 98           # xs: statements (a try statement's finalbody, as its c)

P_PARAMETERS = 100    # xs: posonly P_PARAM_DEFAULT; ys: args; zs: kwonly; a: vararg P_PARAMETER; b: kwarg P_PARAMETER
P_PARAMETER = 101     # s: name, nstart/nend; a: annotation
P_PARAM_DEFAULT = 102  # a: P_PARAMETER; b: default
P_TYPE_PARAMS = 103   # xs: type params
P_TYPEVAR = 104       # s: name; a: bound; b: default
P_PARAMSPEC = 105     # s: name; b: default
P_TYPEVARTUPLE = 106  # s: name; b: default

# expression contexts
CTX_LOAD = 0
CTX_STORE = 1
CTX_DEL = 2
CTX_INVALID = 3


class Node:
    # Sixteen eight-byte fields and two flags, 128 bytes: one more field would take the object
    # past the sizes the allocator serves inline (runtime.c's gc_alloc: under 136 bytes), and
    # every node would cost a call
    def __init__(self, kind: int, start: int, end: int) -> None:
        self.kind: int = kind
        self.start: int = start
        self.end: int = end
        self.a: Node | None = None
        self.b: Node | None = None
        self.c: Node | None = None
        self.xs: list[Node] = EMPTY
        self.ys: list[Node] = EMPTY
        self.zs: list[Node] = EMPTY
        self.ints: list[int] = EMPTY_INTS
        self.s = b""
        self.n = 0
        self.ival = 0
        self.flag = False
        self.flag2 = False
        self.nstart = 0
        self.nend = 0


# shared empty lists: a node's list fields are replaced, never appended to in place
EMPTY: list[Node] = []
EMPTY_INTS: list[int] = []


def child(node: Node | None) -> Node:
    # (the caller knows the child is there)
    assert node is not None
    return node
