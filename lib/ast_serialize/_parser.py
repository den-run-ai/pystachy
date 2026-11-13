"""The parser: Ruff's ruff_python_parser parser (parser/*.rs, string.rs and token_source.rs of
ast_serialize 0.13.1's vendored crates, MIT; see THIRD_PARTY_NOTICES), building _ast.Node trees with
Ruff's ranges, error recovery and messages.
"""
import unicodedata

from ._ast import (
    CTX_DEL, CTX_INVALID, CTX_LOAD, CTX_STORE, E_ATTRIBUTE, E_AWAIT, E_BINOP, E_BOOL, E_BOOLOP,
    E_BYTES, E_CALL, E_COMPARE, E_COMPLEX, E_DICT, E_DICTCOMP, E_ELLIPSIS, E_FLOAT, E_FSTRING,
    E_GENERATOR, E_IF, E_INT, E_LAMBDA, E_LIST, E_LISTCOMP, E_NAME, E_NAMED, E_NONE, E_SET,
    E_SETCOMP, E_SLICE, E_STARRED, E_STRING, E_SUBSCRIPT, E_TSTRING, E_TUPLE, E_UNARYOP,
    E_YIELD, E_YIELDFROM, EMPTY, M_AS, M_CLASS, M_MAPPING, M_OR, M_SEQUENCE, M_SINGLETON, M_STAR,
    M_VALUE, Node, P_PARAM_DEFAULT, P_PARAMETER, P_PARAMETERS, P_PARAMSPEC, P_TYPE_PARAMS,
    P_TYPEVAR, P_TYPEVARTUPLE, S_ANNASSIGN, S_ASSERT, S_ASSIGN, S_AUGASSIGN, S_BREAK, S_CLASSDEF,
    S_CONTINUE, S_DELETE, S_EXPR, S_FOR, S_FUNCTIONDEF, S_GLOBAL, S_IF, S_IMPORT, S_IMPORTFROM,
    S_MATCH, S_NONLOCAL, S_PASS, S_RAISE, S_RETURN, S_TRY, S_TYPEALIAS, S_WHILE, S_WITH,
    X_ALIAS, X_ARGUMENTS, X_BYTES_PART, X_COMPREHENSION, X_DECORATOR, X_DICT_ITEM, X_ELIF_ELSE,
    X_EXCEPT_HANDLER, X_FORMAT_SPEC, X_FS_INTERP, X_FS_LITERAL, X_FSTRING_PART, X_IDENTIFIER,
    X_KEYWORD, X_MATCH_CASE, X_PATTERN_KEYWORD, X_STRING_PART, X_WITHITEM,
)
from ._names16 import lookup as names16_lookup
from ._lexer import (
    F_BYTE, F_FSTRING, F_NON_ASCII_NAME, F_RAW, F_TRIPLE_QUOTED, F_TSTRING, F_UNCLOSED,
    MODE_MODULE, Lexer, LexerCheckpoint, closer_len, opener_len,
)
from ._tokens import (
    KIND_TEXT, N_KINDS, T_AMPER, T_AMPEREQUAL, T_AND, T_AS, T_ASSERT, T_ASYNC, T_AT, T_ATEQUAL,
    T_AWAIT, T_BREAK, T_CASE, T_CIRCUMFLEX, T_CIRCUMFLEXEQUAL, T_CLASS, T_COLON, T_COLONEQUAL,
    T_COMMA, T_COMMENT, T_COMPLEX, T_CONTINUE, T_DEDENT, T_DEF, T_DEL, T_DOT, T_DOUBLESLASH,
    T_DOUBLESLASHEQUAL, T_DOUBLESTAR, T_DOUBLESTAREQUAL, T_ELIF, T_ELLIPSIS, T_ELSE,
    T_ENDOFFILE, T_EQEQUAL, T_EQUAL, T_EXCEPT, T_EXCLAMATION, T_FALSE, T_FINALLY, T_FLOAT, T_FOR,
    T_FROM, T_FSTRINGEND, T_FSTRINGMIDDLE, T_FSTRINGSTART, T_GLOBAL, T_GREATER,
    T_GREATEREQUAL, T_IF, T_IMPORT, T_IN, T_INDENT, T_INT, T_IPYESCAPECOMMAND, T_IS, T_LAMBDA,
    T_LAZY, T_LBRACE, T_LEFTSHIFT, T_LEFTSHIFTEQUAL, T_LESS, T_LESSEQUAL, T_LPAR, T_LSQB,
    T_MATCH, T_MINUS, T_MINUSEQUAL, T_NAME, T_NEWLINE, T_NONE, T_NONLOCAL, T_NONLOGICALNEWLINE,
    T_NOT, T_NOTEQUAL, T_OR, T_PASS, T_PERCENT, T_PERCENTEQUAL, T_PLUS, T_PLUSEQUAL, T_RAISE,
    T_RARROW, T_RBRACE, T_RETURN, T_RIGHTSHIFT, T_RIGHTSHIFTEQUAL, T_RPAR, T_RSQB, T_SEMI,
    T_SLASH, T_SLASHEQUAL, T_STAR, T_STAREQUAL, T_STRING, T_TILDE, T_TRUE, T_TRY,
    T_TSTRINGEND, T_TSTRINGMIDDLE, T_TSTRINGSTART, T_TYPE, T_UNKNOWN, T_VBAR, T_VBAREQUAL,
    T_WHILE, T_WITH, T_YIELD,
)


def tset(kinds: list[int]) -> list[bool]:
    s = [False] * N_KINDS
    for k in kinds:
        s[k] = True
    return s


def tunion(a: list[bool], b: list[bool]) -> list[bool]:
    s = [False] * N_KINDS
    for i in range(N_KINDS):
        s[i] = a[i] or b[i]
    return s


def is_keyword(k: int) -> bool:
    return T_AND <= k <= T_TYPE


def is_soft_keyword(k: int) -> bool:
    return T_CASE <= k <= T_TYPE


NEWLINE_EOF_SET = tset([T_NEWLINE, T_ENDOFFILE])
LITERAL_SET = tset([T_INT, T_FLOAT, T_COMPLEX, T_STRING, T_ELLIPSIS, T_TRUE, T_FALSE, T_NONE])
EXPR_SET = tunion(tset([
    T_NAME, T_MINUS, T_PLUS, T_TILDE, T_STAR, T_DOUBLESTAR, T_LPAR, T_LBRACE, T_LSQB, T_LAMBDA,
    T_AWAIT, T_NOT, T_YIELD, T_FSTRINGSTART, T_TSTRINGSTART, T_IPYESCAPECOMMAND]), LITERAL_SET)
END_EXPR_SET = tset([
    T_ENDOFFILE, T_NEWLINE, T_SEMI, T_COLON, T_RBRACE, T_RSQB, T_RPAR, T_COMMA, T_DEDENT, T_IF,
    T_ELSE, T_AS, T_FROM, T_FOR, T_ASYNC, T_IN, T_EQUAL, T_EXCLAMATION])
END_SEQUENCE_SET = tset([
    T_ENDOFFILE, T_NEWLINE, T_SEMI, T_COLON, T_RBRACE, T_RSQB, T_RPAR, T_DEDENT, T_IF,
    T_ELSE, T_AS, T_FROM, T_FOR, T_ASYNC, T_IN, T_EQUAL, T_EXCLAMATION])
COMPOUND_STMT_SET = tset([T_MATCH, T_IF, T_WITH, T_WHILE, T_FOR, T_TRY, T_DEF, T_CLASS, T_ASYNC, T_AT])
SIMPLE_STMT_SET = tset([
    T_PASS, T_RETURN, T_BREAK, T_CONTINUE, T_GLOBAL, T_NONLOCAL, T_ASSERT, T_YIELD, T_DEL,
    T_RAISE, T_IMPORT, T_FROM, T_TYPE, T_IPYESCAPECOMMAND])
SIMPLE_STMT_WITH_EXPR_SET = tunion(SIMPLE_STMT_SET, EXPR_SET)
STMTS_SET = tunion(SIMPLE_STMT_WITH_EXPR_SET, COMPOUND_STMT_SET)
STRING_START_SET = tset([T_STRING, T_FSTRINGSTART, T_TSTRINGSTART])
UPPER_END_SET = tset([T_COMMA, T_COLON, T_RSQB, T_NEWLINE, T_ENDOFFILE])
STEP_END_SET = tset([T_COMMA, T_RSQB, T_NEWLINE, T_ENDOFFILE])
SLICE_LOWER_END_SET = tset([T_NEWLINE, T_ENDOFFILE, T_RSQB, T_COMMA])
LITERAL_PATTERN_START_SET = tset([T_NONE, T_TRUE, T_FALSE, T_STRING, T_INT, T_FLOAT, T_COMPLEX, T_MINUS])
PATTERN_START_SET = tunion(tset([T_STAR, T_NAME, T_LPAR, T_LSQB, T_LBRACE]), LITERAL_PATTERN_START_SET)
MAPPING_PATTERN_START_SET = tunion(tset([T_DOUBLESTAR, T_NAME]), LITERAL_PATTERN_START_SET)

# recovery contexts (RecoveryContextKind, one bit each, as Ruff's RecoveryContext)
RC_MODULE_STATEMENTS = 1 << 0
RC_BLOCK_STATEMENTS = 1 << 1
RC_ELIF = 1 << 2
RC_EXCEPT = 1 << 3
RC_ASSIGNMENT_TARGETS = 1 << 4
RC_TYPE_PARAMS = 1 << 5
RC_IMPORT_FROM_AS_NAMES_PAREN = 1 << 6
RC_IMPORT_FROM_AS_NAMES = 1 << 7
RC_IMPORT_NAMES = 1 << 8
RC_SLICES = 1 << 9
RC_LIST_ELEMENTS = 1 << 10
RC_SET_ELEMENTS = 1 << 11
RC_DICT_ELEMENTS = 1 << 12
RC_TUPLE_ELEMENTS_PAREN = 1 << 13
RC_TUPLE_ELEMENTS = 1 << 14
RC_SEQUENCE_MATCH_PATTERN = 1 << 15
RC_SEQUENCE_MATCH_PATTERN_LIST = 1 << 16
RC_SEQUENCE_MATCH_PATTERN_TUPLE = 1 << 17
RC_MATCH_PATTERN_MAPPING = 1 << 18
RC_MATCH_PATTERN_CLASS_ARGUMENTS = 1 << 19
RC_ARGUMENTS = 1 << 20
RC_DELETE = 1 << 21
RC_IDENTIFIERS = 1 << 22
RC_FUNCTION_PARAMETERS = 1 << 23
RC_LAMBDA_PARAMETERS = 1 << 24
RC_WITH_ITEMS_PAREN = 1 << 25
RC_WITH_ITEMS_PAREN_EXPR = 1 << 26
RC_WITH_ITEMS = 1 << 27
RC_FSTRING_ELEMENTS = 1 << 28
RC_TSTRING_ELEMENTS = 1 << 29
RC_FSTRING_ELEMENTS_SPEC = 1 << 30
RC_TSTRING_ELEMENTS_SPEC = 1 << 31

# list terminators
LT_NONE = 0
LT_REGULAR = 1
LT_RECOVERY = 2

# ExpressionContext
EC_EXCLUDE_IN = 1
EC_ALLOW_STARRED = 2
EC_STARRED_BITWISE_OR = 4
EC_ALLOW_YIELD = 8
EC_EXCLUDE_FOR = 16
EC_STARRED_CONDITIONAL = EC_ALLOW_STARRED
EC_STARRED_BITWISE = EC_ALLOW_STARRED | EC_STARRED_BITWISE_OR
EC_YIELD_OR_STARRED_BITWISE = EC_STARRED_BITWISE | EC_ALLOW_YIELD

# OperatorPrecedence
PREC_NONE = 0
PREC_YIELD = 1
PREC_ASSIGN = 2
PREC_STARRED = 3
PREC_LAMBDA = 4
PREC_IFELSE = 5
PREC_OR = 6
PREC_AND = 7
PREC_NOT = 8
PREC_COMPARE = 9
PREC_BITOR = 10
PREC_BITXOR = 11
PREC_BITAND = 12
PREC_SHIFT = 13
PREC_ADDSUB = 14
PREC_MULDIV = 15
PREC_POSNEG = 16
PREC_EXPONENT = 17
PREC_AWAIT = 18

# binary operators by token: Ruff's Operator (Add 0 ... FloorDiv 12), or -1
BINOP_OF: list[int] = [-1] * N_KINDS
BINOP_PREC: list[int] = [0] * N_KINDS
AUGOP_OF: list[int] = [-1] * N_KINDS


def _ops() -> None:
    table = [
        (T_PLUS, T_PLUSEQUAL, 0, PREC_ADDSUB), (T_MINUS, T_MINUSEQUAL, 1, PREC_ADDSUB),
        (T_STAR, T_STAREQUAL, 2, PREC_MULDIV), (T_AT, T_ATEQUAL, 3, PREC_MULDIV),
        (T_SLASH, T_SLASHEQUAL, 4, PREC_MULDIV), (T_PERCENT, T_PERCENTEQUAL, 5, PREC_MULDIV),
        (T_DOUBLESTAR, T_DOUBLESTAREQUAL, 6, PREC_EXPONENT),
        (T_LEFTSHIFT, T_LEFTSHIFTEQUAL, 7, PREC_SHIFT), (T_RIGHTSHIFT, T_RIGHTSHIFTEQUAL, 8, PREC_SHIFT),
        (T_VBAR, T_VBAREQUAL, 9, PREC_BITOR), (T_CIRCUMFLEX, T_CIRCUMFLEXEQUAL, 10, PREC_BITXOR),
        (T_AMPER, T_AMPEREQUAL, 11, PREC_BITAND),
        (T_DOUBLESLASH, T_DOUBLESLASHEQUAL, 12, PREC_MULDIV),
    ]
    for tok, aug, op, prec in table:
        BINOP_OF[tok] = op
        BINOP_PREC[tok] = prec
        AUGOP_OF[aug] = op


_ops()
OP_TOKEN: list[int] = [T_PLUS, T_MINUS, T_STAR, T_AT, T_SLASH, T_PERCENT, T_DOUBLESTAR, T_LEFTSHIFT,
                       T_RIGHTSHIFT, T_VBAR, T_CIRCUMFLEX, T_AMPER, T_DOUBLESLASH]
UNARY_TOKEN: list[int] = [T_TILDE, T_NOT, T_PLUS, T_MINUS]
UNARY_TEXT: list[str] = ["~", "not", "+", "-"]

# comparison operators: Eq 0, NotEq 1, Lt 2, LtE 3, Gt 4, GtE 5, Is 6, IsNot 7, In 8, NotIn 9
CMP_IS_NOT = 7
CMP_NOT_IN = 9


def cmp_op(current: int, nxt: int) -> int:
    # helpers::token_kind_to_cmp_op (-1: none)
    if current == T_IS:
        return CMP_IS_NOT if nxt == T_NOT else 6
    if current == T_NOT:
        return CMP_NOT_IN if nxt == T_IN else -1
    if current == T_IN:
        return 8
    if current == T_EQEQUAL:
        return 0
    if current == T_NOTEQUAL:
        return 1
    if current == T_LESS:
        return 2
    if current == T_LESSEQUAL:
        return 3
    if current == T_GREATER:
        return 4
    if current == T_GREATEREQUAL:
        return 5
    return -1


def unary_op(k: int) -> int:
    # TokenKind::as_unary_operator (-1: none)
    if k == T_TILDE:
        return 0
    if k == T_NOT:
        return 1
    if k == T_PLUS:
        return 2
    if k == T_MINUS:
        return 3
    return -1


CLAUSE_TEXT = {
    "if": "`if` statement", "else": "`else` clause", "elif": "`elif` clause",
    "for": "`for` statement", "with": "`with` statement", "class": "`class` definition",
    "while": "`while` statement", "def": "function definition", "case": "`case` block",
    "try": "`try` statement", "except": "`except` clause", "finally": "`finally` clause",
}

MAX_RECURSION_DEPTH = 202


class RecursionLimit(Exception):
    pass


class Parser:
    def __init__(self, src: bytes, mode: int) -> None:
        self.src: bytes = src
        self.mode: int = mode
        self.lexer: Lexer = Lexer(src, mode, 0)
        # every token, trivia too (Ruff's TokenSource::tokens)
        self.tok_kind: list[int] = []
        self.tok_start: list[int] = []
        self.tok_end: list[int] = []
        self.err_start: list[int] = []
        self.err_end: list[int] = []
        self.err_msg: list[str] = []
        self.prev_token_end: int = 0
        self.recovery_context: int = 0
        self.token_id: int = 0
        self.depth_remaining: int = MAX_RECURSION_DEPTH
        self.max_nesting_depth: int = MAX_RECURSION_DEPTH - 2
        self.pp: bool = False  # is_parenthesized of the ParsedExpr last returned
        self.do_bump_lexer()

    # ---------------------------------------------------------------- tokens
    def do_bump_lexer(self) -> None:
        lx = self.lexer
        while True:
            k = lx.next_token()
            if k == T_COMMENT or k == T_NONLOGICALNEWLINE:
                self.tok_kind.append(k)
                self.tok_start.append(lx.start)
                self.tok_end.append(lx.end)
                continue
            break

    def cur(self) -> int:
        return self.lexer.kind

    def at(self, k: int) -> bool:
        return self.lexer.kind == k

    def at_ts(self, ts: list[bool]) -> bool:
        return ts[self.lexer.kind]

    def cur_start(self) -> int:
        return self.lexer.start

    def cur_end(self) -> int:
        return self.lexer.end

    def node_start(self) -> int:
        return self.lexer.start

    def node_end(self, start: int) -> int:
        # node_range(start).end; with node_range_start for the start
        return self.prev_token_end

    def range_start(self, start: int) -> int:
        # node_range(start): empty at prev_token_end if nothing was consumed since start
        if self.prev_token_end <= start:
            return self.prev_token_end
        return start

    def new(self, kind: int, start: int) -> Node:
        # a node of node_range(start)
        if self.prev_token_end <= start:
            return Node(kind, self.prev_token_end, self.prev_token_end)
        return Node(kind, start, self.prev_token_end)

    def missing(self, kind: int) -> Node:
        return Node(kind, self.prev_token_end, self.prev_token_end)

    def do_bump(self, kind: int) -> None:
        lx = self.lexer
        k = lx.kind
        if k != T_DEDENT and k != T_NEWLINE and k != T_SEMI:
            self.prev_token_end = lx.end
        self.tok_kind.append(kind)
        self.tok_start.append(lx.start)
        self.tok_end.append(lx.end)
        self.do_bump_lexer()
        self.token_id += 1

    def bump(self, kind: int) -> None:
        assert self.lexer.kind == kind
        self.do_bump(kind)

    def bump_any(self) -> None:
        assert self.lexer.kind != T_ENDOFFILE
        self.do_bump(self.lexer.kind)

    def eat(self, kind: int) -> bool:
        if self.lexer.kind == kind:
            self.do_bump(kind)
            return True
        return False

    def expect(self, kind: int) -> bool:
        if self.eat(kind):
            return True
        self.add_error("Expected " + KIND_TEXT[kind] + ", found " + KIND_TEXT[self.lexer.kind],
                       self.lexer.start, self.lexer.end)
        return False

    def peek(self) -> int:
        lx = self.lexer
        cp = lx.checkpoint()
        k = self.next_non_trivia()
        lx.rewind(cp)
        return k

    def peek2(self) -> tuple[int, int]:
        lx = self.lexer
        cp = lx.checkpoint()
        k1 = self.next_non_trivia()
        k2 = self.next_non_trivia()
        lx.rewind(cp)
        return k1, k2

    def next_non_trivia(self) -> int:
        lx = self.lexer
        while True:
            k = lx.next_token()
            if k != T_COMMENT and k != T_NONLOGICALNEWLINE:
                return k

    def add_error(self, msg: str, start: int, end: int) -> None:
        n = len(self.err_start)
        if n > 0 and self.err_start[n - 1] == start:
            return
        self.err_start.append(start)
        self.err_end.append(end)
        self.err_msg.append(msg)

    def text(self, start: int, end: int) -> bytes:
        return self.src[start:end]

    def cur_text(self) -> bytes:
        return self.src[self.lexer.start:self.lexer.end]

    def checkpoint(self) -> "ParserCheckpoint":
        return ParserCheckpoint(self.lexer.checkpoint(), len(self.tok_kind), len(self.err_start),
                                self.token_id, self.prev_token_end, self.recovery_context)

    def rewind(self, cp: "ParserCheckpoint") -> None:
        self.lexer.rewind(cp.lexer)
        del self.tok_kind[cp.ntokens:]
        del self.tok_start[cp.ntokens:]
        del self.tok_end[cp.ntokens:]
        del self.err_start[cp.nerrors:]
        del self.err_end[cp.nerrors:]
        del self.err_msg[cp.nerrors:]
        self.token_id = cp.token_id
        self.prev_token_end = cp.prev_token_end
        self.recovery_context = cp.recovery_context

    def re_lex_logical_token(self) -> None:
        nl_start = -1
        nl_index = -1
        i = len(self.tok_kind) - 1
        while i >= 0:
            k = self.tok_kind[i]
            if k == T_NONLOGICALNEWLINE:
                nl_start = self.tok_start[i]
                nl_index = i
            elif k != T_COMMENT:
                break
            i -= 1
        if not self.lexer.re_lex_logical_token(nl_start):
            return
        del self.tok_kind[nl_index:]
        del self.tok_start[nl_index:]
        del self.tok_end[nl_index:]
        # (TokenSource::bump: the trivia token is kept, the parser's position does not move)
        lx = self.lexer
        k = lx.kind
        if k == T_COMMENT or k == T_NONLOGICALNEWLINE:
            self.tok_kind.append(k)
            self.tok_start.append(lx.start)
            self.tok_end.append(lx.end)
            self.do_bump_lexer()

    def finish_tokens(self) -> None:
        # TokenSource::finish: the EndOfFile token is dropped; lexical errors are merged with the
        # parser's by start offset (a lexical error replaces a parse error at the same offset)
        if len(self.tok_kind) > 0 and self.tok_kind[-1] == T_ENDOFFILE:
            self.tok_kind.pop()
            self.tok_start.pop()
            self.tok_end.pop()
        lx = self.lexer
        if len(lx.err_start) == 0:
            return
        ps = self.err_start
        pe = self.err_end
        pm = self.err_msg
        ls = lx.err_start
        le = lx.err_end
        lm = lx.err_msg
        out_s: list[int] = []
        out_e: list[int] = []
        out_m: list[str] = []
        i = 0
        j = 0
        while i < len(ps) and j < len(ls):
            if ps[i] < ls[j]:
                out_s.append(ps[i])
                out_e.append(pe[i])
                out_m.append(pm[i])
                i += 1
            elif ps[i] == ls[j]:
                i += 1
                out_s.append(ls[j])
                out_e.append(le[j])
                out_m.append(lm[j])
                j += 1
            else:
                out_s.append(ls[j])
                out_e.append(le[j])
                out_m.append(lm[j])
                j += 1
        while i < len(ps):
            out_s.append(ps[i])
            out_e.append(pe[i])
            out_m.append(pm[i])
            i += 1
        while j < len(ls):
            out_s.append(ls[j])
            out_e.append(le[j])
            out_m.append(lm[j])
            j += 1
        self.err_start = out_s
        self.err_end = out_e
        self.err_msg = out_m

    def report_recursion_limit_exceeded(self, start: int, end: int) -> None:
        self.add_error("Source is too deeply nested", start, end)
        while self.lexer.kind != T_ENDOFFILE:
            self.bump_any()

    def recursion_recovery_expr(self) -> Node:
        n = self.missing(E_NAME)
        n.n = CTX_INVALID
        self.pp = False
        return n

    # ---------------------------------------------------------------- lists
    def is_list_element(self, rc: int) -> bool:
        k = self.lexer.kind
        if rc == RC_MODULE_STATEMENTS or rc == RC_BLOCK_STATEMENTS:
            return self.at_stmt()
        if rc == RC_ELIF:
            return k == T_ELIF
        if rc == RC_EXCEPT:
            return k == T_EXCEPT
        if rc == RC_ASSIGNMENT_TARGETS:
            return k == T_EQUAL
        if rc == RC_TYPE_PARAMS:
            return self.at_type_param()
        if rc == RC_IMPORT_NAMES:
            return k == T_NAME or is_soft_keyword(k)
        if rc == RC_IMPORT_FROM_AS_NAMES or rc == RC_IMPORT_FROM_AS_NAMES_PAREN:
            return k == T_STAR or k == T_NAME or is_soft_keyword(k)
        if rc == RC_SLICES:
            return k == T_COLON or self.at_expr()
        if rc == RC_LIST_ELEMENTS or rc == RC_SET_ELEMENTS or rc == RC_TUPLE_ELEMENTS or rc == RC_TUPLE_ELEMENTS_PAREN:
            return self.at_expr()
        if rc == RC_DICT_ELEMENTS:
            return k == T_DOUBLESTAR or self.at_expr()
        if rc == RC_SEQUENCE_MATCH_PATTERN or rc == RC_SEQUENCE_MATCH_PATTERN_LIST or rc == RC_SEQUENCE_MATCH_PATTERN_TUPLE:
            return k == T_PLUS or self.at_pattern_start()
        if rc == RC_MATCH_PATTERN_MAPPING:
            return k == T_STAR or self.at_mapping_pattern_start()
        if rc == RC_MATCH_PATTERN_CLASS_ARGUMENTS:
            return self.at_pattern_start()
        if rc == RC_ARGUMENTS or rc == RC_DELETE:
            return self.at_expr()
        if rc == RC_IDENTIFIERS:
            return k == T_NAME or is_soft_keyword(k)
        if rc == RC_FUNCTION_PARAMETERS or rc == RC_LAMBDA_PARAMETERS:
            return k == T_STAR or k == T_DOUBLESTAR or k == T_SLASH or k == T_NAME or is_soft_keyword(k)
        if rc == RC_WITH_ITEMS or rc == RC_WITH_ITEMS_PAREN or rc == RC_WITH_ITEMS_PAREN_EXPR:
            return self.at_expr()
        if rc == RC_FSTRING_ELEMENTS or rc == RC_FSTRING_ELEMENTS_SPEC:
            return k == T_FSTRINGMIDDLE or k == T_LBRACE
        if rc == RC_TSTRING_ELEMENTS or rc == RC_TSTRING_ELEMENTS_SPEC:
            return k == T_TSTRINGMIDDLE or k == T_LBRACE
        return False

    def list_terminator_kind(self, rc: int) -> int:
        k = self.lexer.kind
        if k == T_ENDOFFILE:
            return LT_REGULAR
        if rc == RC_MODULE_STATEMENTS:
            return LT_NONE
        if rc == RC_BLOCK_STATEMENTS:
            return LT_REGULAR if k == T_DEDENT else LT_NONE
        if rc == RC_ELIF:
            return LT_REGULAR if k == T_ELSE else LT_NONE
        if rc == RC_EXCEPT:
            return LT_REGULAR if k == T_FINALLY or k == T_ELSE else LT_NONE
        if rc == RC_ASSIGNMENT_TARGETS:
            return LT_REGULAR if k == T_NEWLINE or k == T_SEMI else LT_NONE
        if rc == RC_TYPE_PARAMS:
            if k == T_RSQB:
                return LT_REGULAR
            return LT_RECOVERY if k == T_NEWLINE or k == T_COLON or k == T_EQUAL or k == T_LPAR else LT_NONE
        if rc == RC_IMPORT_NAMES:
            return LT_REGULAR if k == T_SEMI or k == T_NEWLINE else LT_NONE
        if rc == RC_IMPORT_FROM_AS_NAMES or rc == RC_IMPORT_FROM_AS_NAMES_PAREN:
            return LT_REGULAR if k == T_RPAR or k == T_SEMI or k == T_NEWLINE else LT_NONE
        if rc == RC_SLICES or rc == RC_LIST_ELEMENTS:
            return LT_REGULAR if k == T_RSQB else LT_NONE
        if rc == RC_SET_ELEMENTS or rc == RC_DICT_ELEMENTS:
            return LT_REGULAR if k == T_RBRACE else LT_NONE
        if rc == RC_TUPLE_ELEMENTS_PAREN:
            return LT_REGULAR if k == T_RPAR else LT_NONE
        if rc == RC_TUPLE_ELEMENTS:
            return LT_REGULAR if END_SEQUENCE_SET[k] else LT_NONE
        if rc == RC_SEQUENCE_MATCH_PATTERN:
            return LT_REGULAR if k == T_COLON or k == T_IF else LT_NONE
        if rc == RC_SEQUENCE_MATCH_PATTERN_LIST:
            return LT_REGULAR if k == T_RSQB else LT_NONE
        if rc == RC_SEQUENCE_MATCH_PATTERN_TUPLE:
            return LT_REGULAR if k == T_RPAR else LT_NONE
        if rc == RC_MATCH_PATTERN_MAPPING:
            return LT_REGULAR if k == T_RBRACE else LT_NONE
        if rc == RC_MATCH_PATTERN_CLASS_ARGUMENTS or rc == RC_ARGUMENTS:
            return LT_REGULAR if k == T_RPAR else LT_NONE
        if rc == RC_DELETE or rc == RC_IDENTIFIERS:
            return LT_REGULAR if k == T_SEMI or k == T_NEWLINE else LT_NONE
        if rc == RC_FUNCTION_PARAMETERS or rc == RC_LAMBDA_PARAMETERS:
            term = T_RPAR if rc == RC_FUNCTION_PARAMETERS else T_COLON
            if k == term:
                return LT_REGULAR
            return LT_RECOVERY if k == T_RARROW or COMPOUND_STMT_SET[k] else LT_NONE
        if rc == RC_WITH_ITEMS_PAREN:
            if k == T_RPAR:
                return LT_REGULAR
            return LT_RECOVERY if k == T_COLON else LT_NONE
        if rc == RC_WITH_ITEMS:
            return LT_REGULAR if k == T_COLON or k == T_NEWLINE else LT_NONE
        if rc == RC_WITH_ITEMS_PAREN_EXPR:
            return LT_REGULAR if k == T_COLON else LT_NONE
        if rc == RC_FSTRING_ELEMENTS or rc == RC_TSTRING_ELEMENTS:
            term = T_FSTRINGEND if rc == RC_FSTRING_ELEMENTS else T_TSTRINGEND
            if k == term:
                return LT_REGULAR
            return LT_RECOVERY if k == T_NEWLINE else LT_NONE
        if rc == RC_FSTRING_ELEMENTS_SPEC or rc == RC_TSTRING_ELEMENTS_SPEC:
            if k == T_RBRACE:
                return LT_REGULAR
            return LT_RECOVERY if k == T_NEWLINE else LT_NONE
        return LT_NONE

    def allow_trailing_comma(self, rc: int) -> bool:
        return rc in (RC_SLICES, RC_TUPLE_ELEMENTS, RC_TUPLE_ELEMENTS_PAREN, RC_SET_ELEMENTS,
                      RC_LIST_ELEMENTS, RC_DICT_ELEMENTS, RC_ARGUMENTS, RC_MATCH_PATTERN_MAPPING,
                      RC_SEQUENCE_MATCH_PATTERN, RC_SEQUENCE_MATCH_PATTERN_LIST,
                      RC_SEQUENCE_MATCH_PATTERN_TUPLE, RC_MATCH_PATTERN_CLASS_ARGUMENTS,
                      RC_FUNCTION_PARAMETERS, RC_LAMBDA_PARAMETERS, RC_TYPE_PARAMS, RC_DELETE,
                      RC_IMPORT_FROM_AS_NAMES_PAREN, RC_WITH_ITEMS_PAREN)

    def create_error(self, rc: int) -> str:
        k = self.lexer.kind
        if rc == RC_MODULE_STATEMENTS or rc == RC_BLOCK_STATEMENTS:
            return "Unexpected indentation" if k == T_INDENT else "Expected a statement"
        if rc == RC_ELIF:
            return "Expected an `elif` or `else` clause, or the end of the `if` statement."
        if rc == RC_EXCEPT:
            return "Expected an `except` or `finally` clause or the end of the `try` statement."
        if rc == RC_ASSIGNMENT_TARGETS:
            if is_keyword(k):
                return "The keyword is not allowed as a variable declaration name"
            return "Expected an assignment target"
        if rc == RC_TYPE_PARAMS:
            return "Expected a type parameter or the end of the type parameter list"
        if rc == RC_IMPORT_FROM_AS_NAMES_PAREN:
            return "Expected an import name or a ')'"
        if rc == RC_IMPORT_FROM_AS_NAMES or rc == RC_IMPORT_NAMES:
            return "Expected an import name"
        if rc == RC_SLICES:
            return "Expected an expression or the end of the slice list"
        if rc == RC_LIST_ELEMENTS:
            return "Expected an expression or a ']'"
        if rc == RC_SET_ELEMENTS or rc == RC_DICT_ELEMENTS:
            return "Expected an expression or a '}'"
        if rc == RC_TUPLE_ELEMENTS_PAREN:
            return "Expected an expression or a ')'"
        if rc == RC_TUPLE_ELEMENTS:
            return "Expected an expression"
        if rc == RC_SEQUENCE_MATCH_PATTERN or rc == RC_SEQUENCE_MATCH_PATTERN_LIST or rc == RC_SEQUENCE_MATCH_PATTERN_TUPLE:
            return "Expected a pattern or the end of the sequence pattern"
        if rc == RC_MATCH_PATTERN_MAPPING:
            return "Expected a mapping pattern or the end of the mapping pattern"
        if rc == RC_MATCH_PATTERN_CLASS_ARGUMENTS:
            return "Expected a pattern or a ')'"
        if rc == RC_ARGUMENTS:
            return "Expected an expression or a ')'"
        if rc == RC_DELETE:
            return "Expected a delete target"
        if rc == RC_IDENTIFIERS:
            return "Expected an identifier"
        if rc == RC_FUNCTION_PARAMETERS or rc == RC_LAMBDA_PARAMETERS:
            return "Expected a parameter or the end of the parameter list"
        if rc == RC_WITH_ITEMS_PAREN:
            return "Expected an expression or a ')'"
        if rc == RC_WITH_ITEMS or rc == RC_WITH_ITEMS_PAREN_EXPR:
            return "Expected an expression or the end of the with item list"
        if rc == RC_FSTRING_ELEMENTS:
            return "Expected an element of or the end of the f-string"
        if rc == RC_TSTRING_ELEMENTS:
            return "Expected an element of or the end of the t-string"
        if rc == RC_FSTRING_ELEMENTS_SPEC:
            return "Expected an f-string element or a '}'"
        return "Expected an t-string element or a '}'"

    def is_enclosing_list_element_or_terminator(self) -> bool:
        ctx = self.recovery_context
        bit = 1
        while bit <= ctx:
            if ctx & bit:
                if self.list_terminator_kind(bit) != LT_NONE or self.is_list_element(bit):
                    return True
            bit <<= 1
        return False

    def list_begin(self, rc: int) -> int:
        saved = self.recovery_context
        self.recovery_context = saved | rc
        return saved

    def list_step(self, rc: int, state: list[int]) -> int:
        """One step of parse_list: 1 to parse an element, 0 to stop; state holds [progress token id
        (or -1), unexpected indents]."""
        while True:
            if state[0] == self.token_id:
                raise AssertionError("The parser is no longer progressing")
            state[0] = self.token_id
            if 0 < state[1] and self.at(T_DEDENT):
                state[1] -= 1
                self.bump(T_DEDENT)
                continue
            if self.is_list_element(rc):
                return 1
            if self.list_terminator_kind(rc) == LT_REGULAR:
                return 0
            if self.is_enclosing_list_element_or_terminator():
                self.re_lex_logical_token()
                return 0
            self.add_error(self.create_error(rc), self.lexer.start, self.lexer.end)
            if (rc == RC_MODULE_STATEMENTS or rc == RC_BLOCK_STATEMENTS) and self.at(T_INDENT):
                state[1] += 1
            self.bump_any()

    def sep_step(self, rc: int, state: list[int]) -> int:
        """One step of parse_comma_separated_list: 1 to parse an element, 0 to stop. state holds
        [progress token id (or -1), first element (1/0), trailing comma start, end (-1: none),
        2 if an element was just parsed without a following comma]. After each element, the
        caller calls sep_after()."""
        skip_top = state[4] == 2
        state[4] = 0
        while True:
            if not skip_top:
                if state[0] == self.token_id:
                    raise AssertionError("The parser is no longer progressing")
                state[0] = self.token_id
                if self.is_list_element(rc):
                    return 1
            skip_top = False
            if self.list_terminator_kind(rc) == LT_REGULAR:
                return 0
            if self.is_list_element(rc):
                self.expect(T_COMMA)
                continue
            if self.is_enclosing_list_element_or_terminator():
                self.re_lex_logical_token()
                return 0
            if state[1] == 1 or self.at(T_COMMA):
                self.add_error(self.create_error(rc), self.lexer.start, self.lexer.end)
                if self.at(T_COMMA):
                    state[2] = self.lexer.start
                    state[3] = self.lexer.end
                else:
                    state[2] = -1
                    state[3] = -1
            else:
                self.expect(T_COMMA)
                state[2] = -1
                state[3] = -1
            self.bump_any()

    def sep_after(self, state: list[int]) -> bool:
        # after an element: eat a comma (True: continue with the next element)
        state[1] = 0
        s = self.lexer.start
        e = self.lexer.end
        if self.eat(T_COMMA):
            state[2] = s
            state[3] = e
            state[4] = 0
            return True
        state[2] = -1
        state[3] = -1
        state[4] = 2
        return False

    def sep_end(self, rc: int, state: list[int], saved: int) -> bool:
        if state[2] >= 0 and not self.allow_trailing_comma(rc):
            self.add_error("Trailing comma not allowed", state[2], state[3])
        self.recovery_context = saved
        return state[2] >= 0

    # ---------------------------------------------------------------- predicates
    def at_name_or_keyword(self) -> bool:
        k = self.lexer.kind
        return k == T_NAME or is_keyword(k)

    def at_name_or_soft_keyword(self) -> bool:
        k = self.lexer.kind
        return k == T_NAME or is_soft_keyword(k)

    def at_soft_keyword(self) -> bool:
        return is_soft_keyword(self.lexer.kind)

    def at_expr(self) -> bool:
        k = self.lexer.kind
        return EXPR_SET[k] or is_soft_keyword(k)

    def at_sequence_end(self) -> bool:
        return END_SEQUENCE_SET[self.lexer.kind]

    def at_compound_stmt(self) -> bool:
        return COMPOUND_STMT_SET[self.lexer.kind]

    def at_simple_stmt(self) -> bool:
        k = self.lexer.kind
        return SIMPLE_STMT_WITH_EXPR_SET[k] or is_soft_keyword(k)

    def at_stmt(self) -> bool:
        k = self.lexer.kind
        return STMTS_SET[k] or is_soft_keyword(k)

    def at_type_param(self) -> bool:
        k = self.lexer.kind
        return k == T_STAR or k == T_DOUBLESTAR or k == T_NAME or is_keyword(k)

    def at_pattern_start(self) -> bool:
        k = self.lexer.kind
        return PATTERN_START_SET[k] or is_soft_keyword(k)

    def at_mapping_pattern_start(self) -> bool:
        k = self.lexer.kind
        return MAPPING_PATTERN_START_SET[k] or is_soft_keyword(k)

    # ---------------------------------------------------------------- module
    def parse_module(self) -> list[Node]:
        body: list[Node] = []
        saved = self.list_begin(RC_MODULE_STATEMENTS)
        state = [-1, 0]
        while self.list_step(RC_MODULE_STATEMENTS, state) == 1:
            body.append(self.parse_statement())
        self.recovery_context = saved
        self.bump(T_ENDOFFILE)
        self.finish_tokens()
        return body

    def parse_single_expression(self) -> Node:
        expr = self.parse_expression_list(0)
        self.eat(T_NEWLINE)
        if not self.at(T_ENDOFFILE):
            self.add_error("Unexpected token at the end of an expression", self.lexer.start, self.lexer.end)
            last = -1
            while True:
                if last == self.token_id:
                    raise AssertionError("The parser is no longer progressing")
                last = self.token_id
                if self.at(T_ENDOFFILE):
                    break
                self.bump_any()
        self.bump(T_ENDOFFILE)
        self.finish_tokens()
        return expr

    # ---------------------------------------------------------------- names
    def bump_name(self) -> bytes:
        text = self.cur_text()
        if self.lexer.flags & F_NON_ASCII_NAME:
            text = nfkc(text)
        self.bump(T_NAME)
        return text

    def parse_identifier(self, ctx: int) -> Node:
        # an X_IDENTIFIER (s: id; an empty id for a missing one)
        start = self.lexer.start
        end = self.lexer.end
        k = self.lexer.kind
        if k == T_NAME:
            name = self.bump_name()
            n = Node(X_IDENTIFIER, start, end)
            n.s = name
            return n
        if is_soft_keyword(k):
            n = Node(X_IDENTIFIER, start, end)
            n.s = self.text(start, end)
            self.do_bump(T_NAME)
            return n
        if ((ctx & EC_EXCLUDE_FOR) and (k == T_FOR or (k == T_ASYNC and self.peek() == T_FOR))) or \
                ((ctx & EC_EXCLUDE_IN) and k == T_IN):
            return self.parse_missing_identifier()
        if is_keyword(k):
            self.add_error("Expected an identifier, but found a keyword " + KIND_TEXT[k] +
                           " that cannot be used here", start, end)
            n = Node(X_IDENTIFIER, start, end)
            n.s = self.text(start, end)
            self.bump_any()
            return n
        return self.parse_missing_identifier()

    def parse_missing_identifier(self) -> Node:
        self.add_error("Expected an identifier", self.lexer.start, self.lexer.end)
        return self.missing(X_IDENTIFIER)

    def parse_name(self, ctx: int) -> Node:
        lx = self.lexer
        if lx.kind == T_NAME:
            # (parse_identifier()'s first case, without making its node)
            start = lx.start
            end = lx.end
            name = self.bump_name()
            nn = Node(E_NAME, start, end)
            nn.s = name
            nn.n = CTX_LOAD if len(name) > 0 else CTX_INVALID
            return nn
        ident = self.parse_identifier(ctx)
        n = Node(E_NAME, ident.start, ident.end)
        n.s = ident.s
        n.n = CTX_LOAD if len(ident.s) > 0 else CTX_INVALID
        return n

    def parse_missing_name(self) -> Node:
        ident = self.parse_missing_identifier()
        n = Node(E_NAME, ident.start, ident.end)
        n.n = CTX_INVALID
        return n

    # ---------------------------------------------------------------- expressions
    def parse_expression_list(self, ctx: int) -> Node:
        start = self.node_start()
        expr = self.parse_conditional_expression_or_higher_impl(ctx)
        if self.at(T_COMMA):
            sub = ctx & ~EC_ALLOW_YIELD
            t = self.parse_tuple_expression(expr, start, False, 1, sub)
            self.pp = False
            return t
        return expr

    def parse_named_expression_or_higher(self, ctx: int) -> Node:
        start = self.node_start()
        expr = self.parse_conditional_expression_or_higher_impl(ctx)
        if self.at(T_COLONEQUAL):
            named = self.parse_named_expression(expr, start)
            self.pp = False
            return named
        return expr

    def parse_conditional_expression_or_higher(self) -> Node:
        return self.parse_conditional_expression_or_higher_impl(0)

    def parse_conditional_expression_or_higher_impl(self, ctx: int) -> Node:
        if self.at(T_LAMBDA):
            lam = self.parse_lambda_expr()
            self.pp = False
            return lam
        start = self.node_start()
        expr = self.parse_binary_expression_or_higher(PREC_NONE, ctx)
        if self.at(T_IF):
            ifx = self.parse_if_expression(expr, start)
            self.pp = False
            return ifx
        return expr

    def parse_simple_expression(self, ctx: int) -> Node:
        return self.parse_binary_expression_or_higher(PREC_NONE, ctx)

    def parse_binary_expression_or_higher(self, left_prec: int, ctx: int) -> Node:
        start = self.node_start()
        lhs = self.parse_lhs_expression(left_prec, ctx)
        return self.parse_binary_expression_or_higher_recursive(lhs, left_prec, ctx, start)

    def parse_binary_expression_or_higher_recursive(self, left: Node, left_prec: int, ctx: int, start: int) -> Node:
        paren = self.pp
        last = -1
        while True:
            if last == self.token_id:
                raise AssertionError("The parser is no longer progressing")
            last = self.token_id
            k = self.lexer.kind
            if k == T_IN and ctx & EC_EXCLUDE_IN:
                break
            # BinaryLikeOperator::try_from_tokens
            if k == T_AND or k == T_OR:
                prec = PREC_AND if k == T_AND else PREC_OR
                if prec <= left_prec:
                    break
                left = self.parse_boolean_expression(left, start, 0 if k == T_AND else 1, ctx)
                paren = False
                continue
            op = BINOP_OF[k]
            if op >= 0:
                prec = BINOP_PREC[k]
                if prec == PREC_EXPONENT:
                    if prec < left_prec:
                        break
                elif prec <= left_prec:
                    break
                self.bump(k)
                if prec == PREC_EXPONENT:
                    if self.depth_remaining == 0:
                        self.report_recursion_limit_exceeded(self.lexer.start, self.lexer.end)
                        right = self.recursion_recovery_expr()
                    else:
                        self.depth_remaining -= 1
                        right = self.parse_binary_expression_or_higher(prec, ctx)
                        self.depth_remaining += 1
                else:
                    right = self.parse_binary_expression_or_higher(prec, ctx)
                b = self.new(E_BINOP, start)
                b.a = left
                b.n = op
                b.b = right
                left = b
                paren = False
                continue
            nxt = -1
            if k == T_IS or k == T_NOT:
                nxt = self.peek()
            cop = cmp_op(k, nxt)
            if cop < 0:
                break
            if PREC_COMPARE <= left_prec:
                break
            left = self.parse_comparison_expression(left, start, cop, ctx)
            paren = False
        self.pp = paren
        return left

    def parse_lhs_expression(self, left_prec: int, ctx: int) -> Node:
        k = self.lexer.kind
        if not (unary_op(k) >= 0 or k == T_STAR or k == T_AWAIT or k == T_LAMBDA or k == T_YIELD
                or k == T_FSTRINGSTART or k == T_TSTRINGSTART or k == T_LPAR or k == T_LSQB
                or k == T_LBRACE):
            return self.parse_lhs_expression_inner(left_prec, ctx, k)
        if self.depth_remaining == 0:
            self.report_recursion_limit_exceeded(self.lexer.start, self.lexer.end)
            return self.recursion_recovery_expr()
        self.depth_remaining -= 1
        r = self.parse_lhs_expression_inner(left_prec, ctx, k)
        self.depth_remaining += 1
        return r

    def parse_lhs_expression_inner(self, left_prec: int, ctx: int, k: int) -> Node:
        start = self.node_start()
        uop = unary_op(k)
        if uop >= 0:
            expr = self.parse_unary_expression(uop, ctx)
            if uop == 1:
                if left_prec > PREC_NOT:
                    self.add_error("Boolean 'not' expression cannot be used here", expr.start, expr.end)
            elif left_prec > PREC_POSNEG and left_prec != PREC_EXPONENT:
                self.add_error("Unary '" + UNARY_TEXT[uop] + "' expression cannot be used here", expr.start, expr.end)
            self.pp = False
            return expr
        if k == T_STAR:
            st = self.parse_starred_expression(ctx)
            if left_prec > PREC_NONE or not (ctx & EC_ALLOW_STARRED):
                self.add_error("Starred expression cannot be used here", st.start, st.end)
            self.pp = False
            return st
        if k == T_AWAIT:
            aw = self.parse_await_expression()
            if left_prec >= PREC_AWAIT:
                self.add_error("Await expression cannot be used here", aw.start, aw.end)
            self.pp = False
            return aw
        if k == T_LAMBDA:
            lam = self.parse_lambda_expr()
            self.add_error("Lambda expression cannot be used here", lam.start, lam.end)
            self.pp = False
            return lam
        if k == T_YIELD:
            y = self.parse_yield_expression()
            if left_prec > PREC_NONE or not (ctx & EC_ALLOW_YIELD):
                self.add_error("Yield expression cannot be used here", y.start, y.end)
            self.pp = False
            return y
        lhs = self.parse_atom(ctx)
        paren = self.pp
        expr = self.parse_postfix_expression(lhs, start, ctx)
        self.pp = paren
        return expr

    def parse_expression_with_bitwise_or_precedence(self) -> Node:
        expr = self.parse_conditional_expression_or_higher()
        if self.pp:
            return expr
        k = expr.kind
        name = ""
        if k == E_COMPARE:
            name = "Comparison"
        elif k == E_BOOLOP or (k == E_UNARYOP and expr.n == 1):
            name = "Boolean"
        elif k == E_IF:
            name = "Conditional"
        elif k == E_LAMBDA:
            name = "Lambda"
        else:
            return expr
        self.add_error(name + " expression cannot be used here", expr.start, expr.end)
        self.pp = False
        return expr

    def parse_atom(self, ctx: int) -> Node:
        start = self.node_start()
        k = self.lexer.kind
        if k == T_FLOAT:
            text = strip_underscores(self.cur_text())
            self.bump(T_FLOAT)
            n = self.new(E_FLOAT, start)
            n.fval = float(text.decode())
        elif k == T_COMPLEX:
            text = strip_underscores(self.cur_text())
            self.bump(T_COMPLEX)
            n = self.new(E_COMPLEX, start)
            n.fval = float(text[:len(text) - 1].decode())
        elif k == T_INT:
            n = self.parse_int_literal(start)
        elif k == T_TRUE or k == T_FALSE:
            self.bump(k)
            n = self.new(E_BOOL, start)
            n.flag = k == T_TRUE
        elif k == T_NONE:
            self.bump(T_NONE)
            n = self.new(E_NONE, start)
        elif k == T_ELLIPSIS:
            self.bump(T_ELLIPSIS)
            n = self.new(E_ELLIPSIS, start)
        elif k == T_NAME:
            n = self.parse_name(ctx)
        elif k == T_STRING or k == T_FSTRINGSTART or k == T_TSTRINGSTART:
            n = self.parse_strings()
        elif k == T_LPAR:
            return self.parse_parenthesized_expression()
        elif k == T_LSQB:
            n = self.parse_list_like_expression()
        elif k == T_LBRACE:
            n = self.parse_set_or_dict_like_expression()
        elif is_keyword(k):
            n = self.parse_name(ctx)
        else:
            # (IPython escape commands are an error in a module too)
            self.add_error("Expected an expression", self.lexer.start, self.lexer.end)
            n = self.missing(E_NAME)
            n.n = CTX_INVALID
        self.pp = False
        return n

    def parse_int_literal(self, start: int) -> Node:
        text = self.cur_text()
        self.bump(T_INT)
        n = self.new(E_INT, start)
        set_int_value(n, text)
        return n

    def parse_postfix_expression(self, lhs: Node, start: int, ctx: int) -> Node:
        while True:
            k = self.lexer.kind
            if k == T_LPAR:
                if self.lexer.nesting > self.max_nesting_depth:
                    self.report_recursion_limit_exceeded(self.lexer.start, self.lexer.end)
                    return lhs
                lhs = self.parse_call_expression(lhs, start)
            elif k == T_LSQB:
                if self.lexer.nesting > self.max_nesting_depth:
                    self.report_recursion_limit_exceeded(self.lexer.start, self.lexer.end)
                    return lhs
                lhs = self.parse_subscript_expression(lhs, start)
            elif k == T_DOT:
                lhs = self.parse_attribute_expression(lhs, start, ctx)
            else:
                return lhs

    def parse_call_expression(self, func: Node, start: int) -> Node:
        args = self.parse_arguments(False)
        c = Node(E_CALL, start, args.end)
        c.a = func
        c.b = args
        return c

    def parse_arguments(self, class_def: bool) -> Node:
        start = self.node_start()
        self.bump(T_LPAR)
        if self.eat(T_RPAR):
            return self.new(X_ARGUMENTS, start)
        args: list[Node] = []
        keywords: list[Node] = []
        seen_keyword_argument = False
        seen_keyword_unpacking = False
        saved = self.list_begin(RC_ARGUMENTS)
        state = [-1, 1, -1, -1, 0]
        while self.sep_step(RC_ARGUMENTS, state) == 1:
            argument_start = self.node_start()
            if self.eat(T_DOUBLESTAR):
                value = self.parse_conditional_expression_or_higher()
                kw = self.new(X_KEYWORD, argument_start)
                kw.a = value
                keywords.append(kw)
                seen_keyword_unpacking = True
            else:
                astart = self.node_start()
                expr = self.parse_named_expression_or_higher(EC_STARRED_CONDITIONAL)
                paren = self.pp
                k = self.lexer.kind
                if k == T_ASYNC or k == T_FOR:
                    expr = self.parse_generator_expression(expr, astart, False)
                    paren = False
                elif seen_keyword_unpacking and not paren and expr.kind == E_STARRED:
                    self.add_error("Iterable argument unpacking cannot follow keyword argument unpacking", expr.start, expr.end)
                if self.eat(T_EQUAL):
                    seen_keyword_argument = True
                    kw = Node(X_KEYWORD, 0, 0)
                    kw.flag = True
                    if expr.kind == E_NAME:
                        kw.s = expr.s
                        kw.nstart = expr.start
                        kw.nend = expr.end
                    else:
                        self.add_error("Expected a parameter name", expr.start, expr.end)
                        kw.nstart = expr.start
                        kw.nend = expr.end
                    value = self.parse_conditional_expression_or_higher()
                    kw.a = value
                    kw.start = self.range_start(argument_start)
                    kw.end = self.prev_token_end
                    keywords.append(kw)
                else:
                    if not (not paren and expr.kind == E_STARRED):
                        if seen_keyword_unpacking:
                            self.add_error("Positional argument cannot follow keyword argument unpacking", expr.start, expr.end)
                        elif seen_keyword_argument:
                            self.add_error("Positional argument cannot follow keyword argument", expr.start, expr.end)
                    args.append(expr)
            self.sep_after(state)
        has_trailing_comma = self.sep_end(RC_ARGUMENTS, state, saved)
        self.expect(T_RPAR)
        node = self.new(X_ARGUMENTS, start)
        node.xs = args
        node.ys = keywords
        self.validate_arguments(node, has_trailing_comma, class_def)
        return node

    def validate_arguments(self, arguments: Node, has_trailing_comma: bool, class_def: bool) -> None:
        seen: dict[bytes, bool] = {}
        for kw in arguments.ys:
            if kw.flag:
                if kw.s in seen:
                    self.add_error("Duplicate keyword argument " + debug_str(kw.s), kw.start, kw.end)
                else:
                    seen[kw.s] = True
        if class_def:
            must = True
        else:
            must = has_trailing_comma or len(arguments.xs) + len(arguments.ys) > 1
        if must:
            for arg in arguments.xs:
                if arg.kind == E_GENERATOR and not arg.flag:
                    self.add_error("Unparenthesized generator expression cannot be used here", arg.start, arg.end)

    def parse_subscript_expression(self, value: Node, start: int) -> Node:
        self.bump(T_LSQB)
        set_expr_ctx(value, CTX_LOAD)
        slice_start = self.node_start()
        if self.eat(T_RSQB):
            sl = self.new(E_NAME, slice_start)
            sl.n = CTX_INVALID
            self.add_error("Expected index or slice expression", sl.start, sl.end)
            n = self.new(E_SUBSCRIPT, start)
            n.a = value
            n.b = sl
            return n
        sl = self.parse_slice()
        if self.eat(T_COMMA):
            elts = [sl]
            saved = self.list_begin(RC_SLICES)
            state = [-1, 1, -1, -1, 0]
            while self.sep_step(RC_SLICES, state) == 1:
                elts.append(self.parse_slice())
                self.sep_after(state)
            self.sep_end(RC_SLICES, state, saved)
            sl = self.new(E_TUPLE, slice_start)
            sl.xs = elts
        elif sl.kind == E_STARRED:
            t = self.new(E_TUPLE, slice_start)
            t.xs = [sl]
            sl = t
        self.expect(T_RSQB)
        n = self.new(E_SUBSCRIPT, start)
        n.a = value
        n.b = sl
        return n

    def parse_slice(self) -> Node:
        start = self.node_start()
        lower: Node | None = None
        if self.at_expr():
            low = self.parse_named_expression_or_higher(EC_STARRED_CONDITIONAL)
            paren = self.pp
            if SLICE_LOWER_END_SET[self.lexer.kind]:
                return low
            if not paren:
                if low.kind == E_STARRED:
                    self.add_error("Starred expression cannot be used here", low.start, low.end)
                elif low.kind == E_NAMED:
                    self.add_error("Unparenthesized named expression cannot be used here", low.start, low.end)
            lower = low
        self.expect(T_COLON)
        upper: Node | None = None
        if not UPPER_END_SET[self.lexer.kind]:
            upper = self.parse_conditional_expression_or_higher()
        step: Node | None = None
        if self.eat(T_COLON):
            if not STEP_END_SET[self.lexer.kind]:
                step = self.parse_conditional_expression_or_higher()
        n = self.new(E_SLICE, start)
        n.a = lower
        n.b = upper
        n.c = step
        return n

    def parse_unary_expression(self, op: int, ctx: int) -> Node:
        start = self.node_start()
        self.bump(UNARY_TOKEN[op])
        prec = PREC_NOT if op == 1 else PREC_POSNEG
        operand = self.parse_binary_expression_or_higher(prec, ctx)
        n = self.new(E_UNARYOP, start)
        n.n = op
        n.a = operand
        return n

    def parse_attribute_expression(self, value: Node, start: int, ctx: int) -> Node:
        self.bump(T_DOT)
        lx = self.lexer
        if lx.kind == T_NAME:
            # (parse_identifier()'s first case, without making its node)
            astart = lx.start
            aend = lx.end
            name = self.bump_name()
            na = self.new(E_ATTRIBUTE, start)
            na.a = value
            na.s = name
            na.nstart = astart
            na.nend = aend
            return na
        attr = self.parse_identifier(ctx)
        n = self.new(E_ATTRIBUTE, start)
        n.a = value
        n.s = attr.s
        n.nstart = attr.start
        n.nend = attr.end
        return n

    def parse_boolean_expression(self, lhs: Node, start: int, op: int, ctx: int) -> Node:
        tok = T_AND if op == 0 else T_OR
        prec = PREC_AND if op == 0 else PREC_OR
        self.bump(tok)
        values = [lhs]
        last = -1
        while True:
            if last == self.token_id:
                raise AssertionError("The parser is no longer progressing")
            last = self.token_id
            values.append(self.parse_binary_expression_or_higher(prec, ctx))
            if not self.eat(tok):
                break
        n = self.new(E_BOOLOP, start)
        n.n = op
        n.xs = values
        return n

    def bump_cmp_op(self, op: int) -> None:
        if op == CMP_IS_NOT:
            self.bump(T_IS)
            self.bump(T_NOT)
        elif op == CMP_NOT_IN:
            self.bump(T_NOT)
            self.bump(T_IN)
        else:
            self.bump(self.lexer.kind)

    def parse_comparison_expression(self, lhs: Node, start: int, op: int, ctx: int) -> Node:
        self.bump_cmp_op(op)
        ops = [op]
        comparators: list[Node] = []
        last = -1
        while True:
            if last == self.token_id:
                raise AssertionError("The parser is no longer progressing")
            last = self.token_id
            comparators.append(self.parse_binary_expression_or_higher(PREC_COMPARE, ctx))
            k = self.lexer.kind
            if k == T_IN and ctx & EC_EXCLUDE_IN:
                break
            nxt = -1
            if k == T_IS or k == T_NOT:
                nxt = self.peek()
            nop = cmp_op(k, nxt)
            if nop < 0:
                break
            self.bump_cmp_op(nop)
            ops.append(nop)
        n = self.new(E_COMPARE, start)
        n.a = lhs
        n.ints = ops
        n.ys = comparators
        return n

    # ---------------------------------------------------------------- strings
    def parse_strings(self) -> Node:
        start = self.node_start()
        first = self.parse_string()
        if not STRING_START_SET[self.lexer.kind]:
            return string_expr(first)
        strings = [first]
        last = -1
        while STRING_START_SET[self.lexer.kind]:
            if last == self.token_id:
                raise AssertionError("The parser is no longer progressing")
            last = self.token_id
            strings.append(self.parse_string())
        rs = self.range_start(start)
        return self.handle_implicitly_concatenated_strings(strings, rs, self.prev_token_end)

    def parse_string(self) -> Node:
        # a string part: X_STRING_PART, X_BYTES_PART, or X_FSTRING_PART (n has F_TSTRING for a t-string)
        k = self.lexer.kind
        if k == T_STRING:
            return self.parse_string_or_byte_literal()
        if k == T_FSTRINGSTART:
            return self.parse_interpolated_string(False)
        return self.parse_interpolated_string(True)

    def handle_implicitly_concatenated_strings(self, strings: list[Node], start: int, end: int) -> Node:
        has_fstring = False
        nbytes = 0
        ntstrings = 0
        for s in strings:
            if s.kind == X_FSTRING_PART:
                if s.n & F_TSTRING:
                    ntstrings += 1
                else:
                    has_fstring = True
            elif s.kind == X_BYTES_PART:
                nbytes += 1
        if nbytes > 0:
            if nbytes < len(strings):
                self.add_error("Bytes literal cannot be mixed with non-bytes literals", start, end)
            else:
                n = Node(E_BYTES, start, end)
                n.xs = strings
                return n
        if ntstrings > 0:
            if ntstrings < len(strings):
                self.add_error("Cannot mix t-string literals with string or bytes literals", start, end)
            else:
                n = Node(E_TSTRING, start, end)
                n.xs = strings
                return n
        if not has_fstring and ntstrings == 0:
            parts: list[Node] = []
            for s in strings:
                if s.kind == X_STRING_PART:
                    parts.append(s)
                else:
                    parts.append(invalid_string_part(s))
            n = Node(E_STRING, start, end)
            n.xs = parts
            return n
        parts = []
        for s in strings:
            if s.kind == X_FSTRING_PART and not (s.n & F_TSTRING):
                parts.append(s)
            elif s.kind == X_STRING_PART:
                parts.append(s)
            else:
                parts.append(invalid_string_part(s))
        n = Node(E_FSTRING, start, end)
        n.xs = parts
        return n

    def parse_string_or_byte_literal(self) -> Node:
        start = self.lexer.start
        end = self.lexer.end
        flags = self.lexer.flags
        vstart = start + opener_len(flags)
        vend = end - closer_len(flags)
        self.bump(T_STRING)
        sp = StringParser(self.src, vstart, vend, flags)
        if flags & F_BYTE:
            value = sp.parse_bytes()
            kind = X_BYTES_PART
        else:
            value = sp.parse_string()
            kind = X_STRING_PART
        n = Node(kind, start, end)
        n.n = flags
        if sp.err_msg != "":
            self.add_error(sp.err_msg, sp.err_start, sp.err_end)
            n.flag2 = True  # invalid
        else:
            n.s = value
        return n

    def parse_interpolated_string(self, tstring: bool) -> Node:
        start = self.node_start()
        flags = self.lexer.flags
        self.bump(T_TSTRINGSTART if tstring else T_FSTRINGSTART)
        elements = self.parse_interpolated_string_elements(flags, False, tstring)
        if not self.expect(T_TSTRINGEND if tstring else T_FSTRINGEND):
            flags |= F_UNCLOSED
        n = self.new(X_FSTRING_PART, start)
        n.xs = elements
        n.n = flags
        return n

    def parse_interpolated_string_elements(self, flags: int, spec: bool, tstring: bool) -> list[Node]:
        if tstring:
            rc = RC_TSTRING_ELEMENTS_SPEC if spec else RC_TSTRING_ELEMENTS
            middle = T_TSTRINGMIDDLE
        else:
            rc = RC_FSTRING_ELEMENTS_SPEC if spec else RC_FSTRING_ELEMENTS
            middle = T_FSTRINGMIDDLE
        elements: list[Node] = []
        saved = self.list_begin(rc)
        state = [-1, 0]
        while self.list_step(rc, state) == 1:
            k = self.lexer.kind
            if k == T_LBRACE:
                elements.append(self.parse_interpolated_element(flags, tstring))
            elif k == middle:
                start = self.lexer.start
                end = self.lexer.end
                self.bump(middle)
                sp = StringParser(self.src, start, end, flags)
                value = sp.parse_fstring_middle()
                lit = Node(X_FS_LITERAL, start, end)
                if sp.err_msg != "":
                    self.add_error(sp.err_msg, sp.err_start, sp.err_end)
                else:
                    lit.s = value
                elements.append(lit)
            elif k == T_UNKNOWN:
                self.bump_any()
            else:
                raise AssertionError("unexpected token in an f-string")
        self.recovery_context = saved
        return elements

    def parse_interpolated_element(self, flags: int, tstring: bool) -> Node:
        prefix = "t-string: " if tstring else "f-string: "
        end_kind = T_TSTRINGEND if tstring else T_FSTRINGEND
        start = self.node_start()
        self.bump(T_LBRACE)
        self.re_lex_string_in_interpolation(end_kind)
        value = self.parse_expression_list(EC_YIELD_OR_STARRED_BITWISE)
        paren = self.pp
        if not paren and value.kind == E_LAMBDA:
            self.add_error(prefix + "lambda expressions are not allowed without parentheses", value.start, value.end)
        node = Node(X_FS_INTERP, 0, 0)
        node.a = value
        if self.eat(T_EQUAL):
            node.flag = True
            node.s = self.text(start + 1, value.start)
            node.s2 = self.text(value.end, self.lexer.start)
        node.n = -1
        if self.eat(T_EXCLAMATION):
            self.lexer.re_lex_raw_string_in_format_spec()
            cstart = self.lexer.start
            cend = self.lexer.end
            if self.at(T_NAME):
                if self.prev_token_end != cstart:
                    self.add_error(prefix + "conversion type must come right after the exclamation mark",
                                   self.prev_token_end, cstart)
                name = self.bump_name()
                if name == b"s":
                    node.n = 115
                elif name == b"r":
                    node.n = 114
                elif name == b"a":
                    node.n = 97
                else:
                    self.add_error(prefix + "invalid conversion character", cstart, cend)
            else:
                self.add_error(prefix + "invalid conversion character", cstart, cend)
                self.bump_any()
        if self.eat(T_COLON):
            spec_start = self.node_start()
            if self.depth_remaining == 0:
                self.report_recursion_limit_exceeded(self.lexer.start, self.lexer.end)
                elements: list[Node] = []
            else:
                self.depth_remaining -= 1
                elements = self.parse_interpolated_string_elements(flags, True, tstring)
                self.depth_remaining += 1
            spec = self.new(X_FORMAT_SPEC, spec_start)
            spec.xs = elements
            node.b = spec
        self.re_lex_string_in_interpolation(end_kind)
        if not self.eat(T_RBRACE):
            self.add_error(prefix + "expecting `}`", self.lexer.start, self.lexer.end)
        node.start = self.range_start(start)
        node.end = self.prev_token_end
        return node

    def re_lex_string_in_interpolation(self, end_kind: int) -> None:
        self.lexer.re_lex_string_in_interpolation(end_kind)

    # ---------------------------------------------------------------- displays
    def parse_list_like_expression(self) -> Node:
        start = self.node_start()
        self.bump(T_LSQB)
        if NEWLINE_EOF_SET[self.lexer.kind]:
            self.add_error("Missing closing bracket `]`", self.lexer.start, self.lexer.end)
        if self.eat(T_RSQB):
            return self.new(E_LIST, start)
        first = self.parse_named_expression_or_higher(EC_STARRED_BITWISE | EC_EXCLUDE_FOR)
        k = self.lexer.kind
        if k == T_ASYNC or k == T_FOR:
            gens = self.parse_generators()
            self.expect(T_RSQB)
            n = self.new(E_LISTCOMP, start)
            n.a = first
            n.xs = gens
            return n
        if not self.at_sequence_end():
            self.expect(T_COMMA)
        elts = [first]
        saved = self.list_begin(RC_LIST_ELEMENTS)
        state = [-1, 1, -1, -1, 0]
        while self.sep_step(RC_LIST_ELEMENTS, state) == 1:
            elts.append(self.parse_named_expression_or_higher(EC_STARRED_BITWISE))
            self.sep_after(state)
        self.sep_end(RC_LIST_ELEMENTS, state, saved)
        self.expect(T_RSQB)
        n = self.new(E_LIST, start)
        n.xs = elts
        return n

    def parse_set_or_dict_like_expression(self) -> Node:
        start = self.node_start()
        self.bump(T_LBRACE)
        if NEWLINE_EOF_SET[self.lexer.kind]:
            self.add_error("Missing closing brace `}`", self.lexer.start, self.lexer.end)
        if self.eat(T_RBRACE):
            return self.new(E_DICT, start)
        after_brace = self.node_start()
        if self.eat(T_DOUBLESTAR):
            value = self.parse_expression_with_bitwise_or_precedence()
            k = self.lexer.kind
            if k == T_ASYNC or k == T_FOR:
                return self.parse_dictionary_comprehension_expression(None, value, start)
            if self.at(T_COLON):
                self.add_error("Starred expression cannot be used here", after_brace, value.end)
                self.bump(T_COLON)
                dict_value = self.parse_conditional_expression_or_higher()
                k = self.lexer.kind
                if k == T_ASYNC or k == T_FOR:
                    return self.parse_dictionary_comprehension_expression(value, dict_value, start)
                return self.parse_dictionary_expression(value, dict_value, start)
            return self.parse_dictionary_expression(None, value, start)
        key = self.parse_named_expression_or_higher(EC_STARRED_BITWISE | EC_EXCLUDE_FOR)
        paren = self.pp
        k = self.lexer.kind
        if k == T_ASYNC or k == T_FOR:
            gens = self.parse_generators()
            self.expect(T_RBRACE)
            n = self.new(E_SETCOMP, start)
            n.a = key
            n.xs = gens
            return n
        if k == T_COLON:
            if not paren:
                if key.kind == E_STARRED:
                    self.add_error("Starred expression cannot be used here", key.start, key.end)
                elif key.kind == E_NAMED:
                    self.add_error("Unparenthesized named expression cannot be used here", key.start, key.end)
            self.bump(T_COLON)
            if self.at(T_DOUBLESTAR):
                unpack_start = self.node_start()
                self.bump(T_DOUBLESTAR)
                value = self.parse_expression_with_bitwise_or_precedence()
                self.add_error("Starred expression cannot be used here", unpack_start, value.end)
            else:
                value = self.parse_conditional_expression_or_higher()
            k = self.lexer.kind
            if k == T_ASYNC or k == T_FOR:
                return self.parse_dictionary_comprehension_expression(key, value, start)
            return self.parse_dictionary_expression(key, value, start)
        # a set
        if not self.at_sequence_end():
            self.expect(T_COMMA)
        elts = [key]
        saved = self.list_begin(RC_SET_ELEMENTS)
        state = [-1, 1, -1, -1, 0]
        while self.sep_step(RC_SET_ELEMENTS, state) == 1:
            elts.append(self.parse_named_expression_or_higher(EC_STARRED_BITWISE))
            self.sep_after(state)
        self.sep_end(RC_SET_ELEMENTS, state, saved)
        self.expect(T_RBRACE)
        n = self.new(E_SET, start)
        n.xs = elts
        return n

    def parse_parenthesized_expression(self) -> Node:
        start = self.node_start()
        self.bump(T_LPAR)
        if NEWLINE_EOF_SET[self.lexer.kind]:
            self.add_error("Missing closing parenthesis `)`", self.lexer.start, self.lexer.end)
        if self.eat(T_RPAR):
            t = self.new(E_TUPLE, start)
            t.flag = True
            self.pp = False
            return t
        expr = self.parse_named_expression_or_higher(EC_YIELD_OR_STARRED_BITWISE | EC_EXCLUDE_FOR)
        k = self.lexer.kind
        if k == T_COMMA:
            t = self.parse_tuple_expression(expr, start, True, 2, EC_STARRED_BITWISE)
            self.pp = False
            return t
        if k == T_ASYNC or k == T_FOR:
            g = self.parse_generator_expression(expr, start, True)
            self.pp = False
            return g
        if expr.kind == E_STARRED:
            self.add_error("Starred expression cannot be used here", expr.start, expr.end)
        self.expect(T_RPAR)
        self.pp = True
        return expr

    def parse_tuple_expression(self, first: Node, start: int, parenthesized: bool, how: int, ctx: int) -> Node:
        """how: 1 parse_conditional_expression_or_higher_impl(ctx), 2
        parse_named_expression_or_higher(ctx) for the elements after the first."""
        if not self.at_sequence_end():
            self.expect(T_COMMA)
        elts = [first]
        rc = RC_TUPLE_ELEMENTS_PAREN if parenthesized else RC_TUPLE_ELEMENTS
        saved = self.list_begin(rc)
        state = [-1, 1, -1, -1, 0]
        while self.sep_step(rc, state) == 1:
            if how == 1:
                elts.append(self.parse_conditional_expression_or_higher_impl(ctx))
            else:
                elts.append(self.parse_named_expression_or_higher(ctx))
            self.sep_after(state)
        self.sep_end(rc, state, saved)
        if parenthesized:
            self.expect(T_RPAR)
        n = self.new(E_TUPLE, start)
        n.xs = elts
        n.flag = parenthesized
        return n

    def parse_dictionary_expression(self, key: Node | None, value: Node, start: int) -> Node:
        if not self.at_sequence_end():
            self.expect(T_COMMA)
        item = Node(X_DICT_ITEM, 0, 0)
        item.a = key
        item.b = value
        items = [item]
        saved = self.list_begin(RC_DICT_ELEMENTS)
        state = [-1, 1, -1, -1, 0]
        while self.sep_step(RC_DICT_ELEMENTS, state) == 1:
            it = Node(X_DICT_ITEM, 0, 0)
            if self.eat(T_DOUBLESTAR):
                it.b = self.parse_expression_with_bitwise_or_precedence()
            else:
                it.a = self.parse_conditional_expression_or_higher()
                self.expect(T_COLON)
                it.b = self.parse_conditional_expression_or_higher()
            items.append(it)
            self.sep_after(state)
        self.sep_end(RC_DICT_ELEMENTS, state, saved)
        self.expect(T_RBRACE)
        n = self.new(E_DICT, start)
        n.xs = items
        return n

    def parse_generators(self) -> list[Node]:
        gens: list[Node] = []
        last = -1
        while self.at(T_FOR) or self.at(T_ASYNC):
            if last == self.token_id:
                raise AssertionError("The parser is no longer progressing")
            last = self.token_id
            gens.append(self.parse_comprehension())
        return gens

    def parse_comprehension(self) -> Node:
        start = self.node_start()
        is_async = self.eat(T_ASYNC)
        if is_async:
            self.expect(T_FOR)
        else:
            self.bump(T_FOR)
        target = self.parse_expression_list(EC_STARRED_CONDITIONAL | EC_EXCLUDE_IN)
        set_expr_ctx(target, CTX_STORE)
        self.validate_assignment_target(target)
        self.expect(T_IN)
        it = self.parse_simple_expression(0)
        ifs: list[Node] = []
        last = -1
        while self.eat(T_IF):
            if last == self.token_id:
                raise AssertionError("The parser is no longer progressing")
            last = self.token_id
            ifs.append(self.parse_simple_expression(0))
        n = self.new(X_COMPREHENSION, start)
        n.a = target
        n.b = it
        n.xs = ifs
        n.flag = is_async
        return n

    def parse_generator_expression(self, element: Node, start: int, parenthesized: bool) -> Node:
        gens = self.parse_generators()
        if parenthesized:
            self.expect(T_RPAR)
        n = self.new(E_GENERATOR, start)
        n.a = element
        n.xs = gens
        n.flag = parenthesized
        return n

    def parse_dictionary_comprehension_expression(self, key: Node | None, value: Node, start: int) -> Node:
        gens = self.parse_generators()
        self.expect(T_RBRACE)
        n = self.new(E_DICTCOMP, start)
        n.a = key
        n.b = value
        n.xs = gens
        return n

    def parse_starred_expression(self, ctx: int) -> Node:
        start = self.node_start()
        self.bump(T_STAR)
        if ctx & EC_STARRED_BITWISE_OR:
            value = self.parse_expression_with_bitwise_or_precedence()
        else:
            value = self.parse_conditional_expression_or_higher_impl(ctx & ~EC_ALLOW_STARRED)
        n = self.new(E_STARRED, start)
        n.a = value
        return n

    def parse_await_expression(self) -> Node:
        start = self.node_start()
        self.bump(T_AWAIT)
        value = self.parse_binary_expression_or_higher(PREC_AWAIT, 0)
        n = self.new(E_AWAIT, start)
        n.a = value
        return n

    def parse_yield_expression(self) -> Node:
        start = self.node_start()
        self.bump(T_YIELD)
        if self.eat(T_FROM):
            value = self.parse_expression_list(0)
            if value.kind == E_TUPLE and not value.flag:
                self.add_error("Unparenthesized tuple expression cannot be used here", value.start, value.end)
            n = self.new(E_YIELDFROM, start)
            n.a = value
            return n
        v: Node | None = None
        if self.at_expr():
            v = self.parse_expression_list(EC_STARRED_BITWISE)
        n = self.new(E_YIELD, start)
        n.a = v
        return n

    def parse_named_expression(self, target: Node, start: int) -> Node:
        self.bump(T_COLONEQUAL)
        if target.kind != E_NAME:
            self.add_error("Assignment expression target must be an identifier", target.start, target.end)
        set_expr_ctx(target, CTX_STORE)
        value = self.parse_conditional_expression_or_higher()
        n = self.new(E_NAMED, start)
        n.a = target
        n.b = value
        return n

    def parse_lambda_expr(self) -> Node:
        start = self.node_start()
        self.bump(T_LAMBDA)
        params: Node | None = None
        if not self.at(T_COLON):
            params = self.parse_parameters(False)
        self.expect(T_COLON)
        if self.depth_remaining == 0:
            self.report_recursion_limit_exceeded(self.lexer.start, self.lexer.end)
            body = self.recursion_recovery_expr()
        else:
            self.depth_remaining -= 1
            body = self.parse_conditional_expression_or_higher()
            self.depth_remaining += 1
        n = self.new(E_LAMBDA, start)
        n.a = params
        n.b = body
        return n

    def parse_if_expression(self, body: Node, start: int) -> Node:
        self.bump(T_IF)
        test = self.parse_simple_expression(0)
        self.expect(T_ELSE)
        if self.depth_remaining == 0:
            self.report_recursion_limit_exceeded(self.lexer.start, self.lexer.end)
            orelse = self.recursion_recovery_expr()
        else:
            self.depth_remaining -= 1
            orelse = self.parse_conditional_expression_or_higher()
            self.depth_remaining += 1
        n = self.new(E_IF, start)
        n.a = body
        n.b = test
        n.c = orelse
        return n

    # ---------------------------------------------------------------- statements
    def parse_statement(self) -> Node:
        start = self.node_start()
        k = self.lexer.kind
        if k == T_IF:
            return self.parse_if_statement()
        if k == T_FOR:
            return self.parse_for_statement(start)
        if k == T_WHILE:
            return self.parse_while_statement()
        if k == T_DEF:
            return self.parse_function_definition(EMPTY, start)
        if k == T_CLASS:
            return self.parse_class_definition(EMPTY, start)
        if k == T_TRY:
            return self.parse_try_statement()
        if k == T_WITH:
            return self.parse_with_statement(start)
        if k == T_AT:
            return self.parse_decorators()
        if k == T_ASYNC:
            return self.parse_async_statement()
        if k == T_MATCH:
            mk = self.classify_match_token()
            if mk == 0:
                return self.parse_match_statement()
            if mk == 2:
                m = self.try_parse_match_statement()
                if m is not None:
                    return m
        return self.parse_single_simple_statement()

    def parse_single_simple_statement(self) -> Node:
        stmt = self.parse_simple_statement()
        has_semi = self.eat(T_SEMI)
        has_newline = self.eat(T_NEWLINE)
        if not has_newline:
            if not has_semi and self.at_simple_stmt():
                self.add_error("Simple statements must be separated by newlines or semicolons",
                               self.lexer.start, self.lexer.end)
            elif self.at_compound_stmt():
                self.add_error("Compound statements are not allowed on the same line as simple statements",
                               self.lexer.start, self.lexer.end)
        return stmt

    def parse_simple_statements(self) -> list[Node]:
        stmts: list[Node] = []
        last = -1
        while True:
            if last == self.token_id:
                raise AssertionError("The parser is no longer progressing")
            last = self.token_id
            stmts.append(self.parse_simple_statement())
            if not self.eat(T_SEMI):
                if self.at_simple_stmt():
                    self.add_error("Simple statements must be separated by newlines or semicolons",
                                   self.lexer.start, self.lexer.end)
                else:
                    break
            if not self.at_simple_stmt():
                break
        if not self.eat(T_NEWLINE):
            if self.at_compound_stmt():
                self.add_error("Compound statements are not allowed on the same line as simple statements",
                               self.lexer.start, self.lexer.end)
            else:
                self.add_error("Expected newline, found " + KIND_TEXT[self.lexer.kind],
                               self.lexer.start, self.lexer.end)
        return stmts

    def parse_simple_statement(self) -> Node:
        k = self.lexer.kind
        if k == T_RETURN:
            return self.parse_return_statement()
        if k == T_IMPORT:
            return self.parse_import_statement(self.node_start(), False)
        if k == T_FROM:
            return self.parse_from_import_statement(self.node_start(), False)
        if k == T_PASS or k == T_CONTINUE or k == T_BREAK:
            start = self.node_start()
            self.bump(k)
            return self.new(S_PASS if k == T_PASS else (S_CONTINUE if k == T_CONTINUE else S_BREAK), start)
        if k == T_RAISE:
            return self.parse_raise_statement()
        if k == T_DEL:
            return self.parse_delete_statement()
        if k == T_ASSERT:
            return self.parse_assert_statement()
        if k == T_GLOBAL or k == T_NONLOCAL:
            return self.parse_global_statement(k)
        if k == T_IPYESCAPECOMMAND:
            # (a module has no IPython escape commands: Ruff reports and keeps one; the serializer panics)
            raise AssertionError("IPython escape command")
        if k == T_LAZY:
            start = self.node_start()
            nk = self.peek()
            if nk == T_IMPORT:
                self.bump(T_LAZY)
                return self.parse_import_statement(start, True)
            if nk == T_FROM:
                self.bump(T_LAZY)
                return self.parse_from_import_statement(start, True)
        if k == T_TYPE:
            first, second = self.peek2()
            if (first == T_NAME or is_soft_keyword(first)) and (second == T_LSQB or second == T_EQUAL):
                return self.parse_type_alias_statement()
        start = self.node_start()
        expr = self.parse_expression_list(EC_YIELD_OR_STARRED_BITWISE)
        paren = self.pp
        if self.at(T_EQUAL):
            return self.parse_assign_statement(expr, start)
        if self.at(T_COLON):
            return self.parse_annotated_assignment_statement(expr, paren, start)
        op = AUGOP_OF[self.lexer.kind]
        if op >= 0:
            return self.parse_augmented_assignment_statement(expr, op, start)
        n = self.new(S_EXPR, start)
        n.a = expr
        return n

    def parse_delete_statement(self) -> Node:
        start = self.node_start()
        self.bump(T_DEL)
        targets: list[Node] = []
        saved = self.list_begin(RC_DELETE)
        state = [-1, 1, -1, -1, 0]
        while self.sep_step(RC_DELETE, state) == 1:
            t = self.parse_conditional_expression_or_higher_impl(EC_STARRED_CONDITIONAL)
            set_expr_ctx(t, CTX_DEL)
            self.validate_delete_target(t)
            targets.append(t)
            self.sep_after(state)
        self.sep_end(RC_DELETE, state, saved)
        if len(targets) == 0:
            self.add_error("Delete statement must have at least one target", self.lexer.start, self.lexer.end)
        n = self.new(S_DELETE, start)
        n.xs = targets
        return n

    def parse_return_statement(self) -> Node:
        start = self.node_start()
        self.bump(T_RETURN)
        v: Node | None = None
        if self.at_expr():
            v = self.parse_expression_list(EC_STARRED_BITWISE)
        n = self.new(S_RETURN, start)
        n.a = v
        return n

    def parse_raise_statement(self) -> Node:
        start = self.node_start()
        self.bump(T_RAISE)
        exc: Node | None = None
        k = self.lexer.kind
        if k == T_NEWLINE:
            pass
        elif k == T_FROM:
            self.add_error("Exception missing in `raise` statement with cause", self.lexer.start, self.lexer.end)
        else:
            e = self.parse_expression_list(0)
            if e.kind == E_TUPLE and not e.flag:
                self.add_error("Unparenthesized tuple expression cannot be used here", e.start, e.end)
            exc = e
        cause: Node | None = None
        if self.eat(T_FROM):
            c = self.parse_expression_list(0)
            if c.kind == E_TUPLE and not c.flag:
                self.add_error("Unparenthesized tuple expression cannot be used here", c.start, c.end)
            cause = c
        n = self.new(S_RAISE, start)
        n.a = exc
        n.b = cause
        return n

    def parse_import_statement(self, start: int, lazy: bool) -> Node:
        self.bump(T_IMPORT)
        names: list[Node] = []
        saved = self.list_begin(RC_IMPORT_NAMES)
        state = [-1, 1, -1, -1, 0]
        while self.sep_step(RC_IMPORT_NAMES, state) == 1:
            names.append(self.parse_alias(True))
            self.sep_after(state)
        self.sep_end(RC_IMPORT_NAMES, state, saved)
        if len(names) == 0:
            self.add_error("Expected one or more symbol names after import", self.lexer.start, self.lexer.end)
        n = self.new(S_IMPORT, start)
        n.xs = names
        n.flag = lazy
        return n

    def parse_from_import_statement(self, start: int, lazy: bool) -> Node:
        self.bump(T_FROM)
        dots = 0
        last = -1
        while True:
            if last == self.token_id:
                raise AssertionError("The parser is no longer progressing")
            last = self.token_id
            if self.eat(T_DOT):
                dots += 1
            elif self.eat(T_ELLIPSIS):
                dots += 3
            else:
                break
        module: Node | None = None
        if self.at_name_or_soft_keyword():
            module = self.parse_dotted_name()
        elif dots == 0:
            self.add_error("Expected a module name", self.lexer.start, self.lexer.end)
        self.expect(T_IMPORT)
        names_start = self.node_start()
        names: list[Node] = []
        seen_star = False
        parenthesized = self.eat(T_LPAR)
        rc = RC_IMPORT_FROM_AS_NAMES_PAREN if parenthesized else RC_IMPORT_FROM_AS_NAMES
        saved = self.list_begin(rc)
        state = [-1, 1, -1, -1, 0]
        while self.sep_step(rc, state) == 1:
            alias = self.parse_alias(False)
            if alias.s == b"*":
                seen_star = True
            names.append(alias)
            self.sep_after(state)
        self.sep_end(rc, state, saved)
        if len(names) == 0:
            self.add_error("Expected one or more symbol names after import", self.lexer.start, self.lexer.end)
        if seen_star and parenthesized:
            self.add_error("Star import cannot be parenthesized", self.range_start(names_start), self.prev_token_end)
        if seen_star and len(names) > 1:
            self.add_error("Star import must be the only import", self.range_start(names_start), self.prev_token_end)
        if parenthesized:
            self.expect(T_RPAR)
        n = self.new(S_IMPORTFROM, start)
        if module is not None:
            n.s = module.s
            n.flag2 = True
        n.xs = names
        n.n = dots
        n.flag = lazy
        return n

    def parse_alias(self, import_style: bool) -> Node:
        start = self.node_start()
        if self.eat(T_STAR):
            a = self.new(X_ALIAS, start)
            a.s = b"*"
            a.nstart = a.start
            a.nend = a.end
            return a
        if import_style:
            name = self.parse_dotted_name()
        else:
            name = self.parse_identifier(0)
        a = Node(X_ALIAS, 0, 0)
        a.s = name.s
        a.nstart = name.start
        a.nend = name.end
        if self.eat(T_AS):
            if self.at_name_or_soft_keyword():
                asname = self.parse_identifier(0)
                a.flag = True
                a.s2 = asname.s
            else:
                self.add_error("Expected symbol after `as`", self.lexer.start, self.lexer.end)
        a.start = self.range_start(start)
        a.end = self.prev_token_end
        return a

    def parse_dotted_name(self) -> Node:
        start = self.node_start()
        first = self.parse_identifier(0)
        if not self.at(T_DOT):
            return first
        parts = [first.s]
        last = -1
        while self.eat(T_DOT):
            if last == self.token_id:
                raise AssertionError("The parser is no longer progressing")
            last = self.token_id
            parts.append(self.parse_identifier(0).s)
        n = self.new(X_IDENTIFIER, start)
        n.s = b".".join(parts)
        return n

    def parse_assert_statement(self) -> Node:
        start = self.node_start()
        self.bump(T_ASSERT)
        test = self.parse_conditional_expression_or_higher()
        msg: Node | None = None
        if self.eat(T_COMMA):
            if self.at_expr():
                msg = self.parse_conditional_expression_or_higher()
            else:
                self.add_error("Expected an expression", self.lexer.start, self.lexer.end)
        n = self.new(S_ASSERT, start)
        n.a = test
        n.b = msg
        return n

    def parse_global_statement(self, k: int) -> Node:
        start = self.node_start()
        self.bump(k)
        names: list[Node] = []
        saved = self.list_begin(RC_IDENTIFIERS)
        state = [-1, 1, -1, -1, 0]
        while self.sep_step(RC_IDENTIFIERS, state) == 1:
            names.append(self.parse_identifier(0))
            self.sep_after(state)
        self.sep_end(RC_IDENTIFIERS, state, saved)
        if len(names) == 0:
            if k == T_GLOBAL:
                self.add_error("Global statement must have at least one name", self.lexer.start, self.lexer.end)
            else:
                self.add_error("Nonlocal statement must have at least one name", self.lexer.start, self.lexer.end)
        n = self.new(S_GLOBAL if k == T_GLOBAL else S_NONLOCAL, start)
        n.xs = names
        return n

    def parse_type_alias_statement(self) -> Node:
        start = self.node_start()
        self.bump(T_TYPE)
        name = self.parse_name(0)
        set_expr_ctx(name, CTX_STORE)
        tparams = self.try_parse_type_params()
        self.expect(T_EQUAL)
        value = self.parse_conditional_expression_or_higher()
        n = self.new(S_TYPEALIAS, start)
        n.a = name
        n.c = tparams
        n.b = value
        return n

    def parse_assign_statement(self, target: Node, start: int) -> Node:
        self.bump(T_EQUAL)
        targets = [target]
        value = self.parse_expression_list(EC_YIELD_OR_STARRED_BITWISE)
        if self.at(T_EQUAL):
            saved = self.list_begin(RC_ASSIGNMENT_TARGETS)
            state = [-1, 0]
            while self.list_step(RC_ASSIGNMENT_TARGETS, state) == 1:
                self.bump(T_EQUAL)
                e = self.parse_expression_list(EC_YIELD_OR_STARRED_BITWISE)
                targets.append(value)
                value = e
            self.recovery_context = saved
        for t in targets:
            set_expr_ctx(t, CTX_STORE)
            self.validate_assignment_target(t)
        n = self.new(S_ASSIGN, start)
        n.xs = targets
        n.a = value
        return n

    def parse_annotated_assignment_statement(self, target: Node, paren: bool, start: int) -> Node:
        self.bump(T_COLON)
        self.validate_annotated_assignment_target(target)
        set_expr_ctx(target, CTX_STORE)
        simple = target.kind == E_NAME and not paren
        annotation = self.parse_conditional_expression_or_higher()
        value: Node | None = None
        if self.eat(T_EQUAL):
            if self.at_expr():
                value = self.parse_expression_list(EC_YIELD_OR_STARRED_BITWISE)
            else:
                self.add_error("Expected an expression", self.lexer.start, self.lexer.end)
        n = self.new(S_ANNASSIGN, start)
        n.a = target
        n.b = annotation
        n.c = value
        n.flag = simple
        return n

    def parse_augmented_assignment_statement(self, target: Node, op: int, start: int) -> Node:
        self.bump_any()
        if target.kind != E_NAME and target.kind != E_ATTRIBUTE and target.kind != E_SUBSCRIPT:
            self.add_error("Invalid augmented assignment target", target.start, target.end)
        set_expr_ctx(target, CTX_STORE)
        value = self.parse_expression_list(EC_YIELD_OR_STARRED_BITWISE)
        n = self.new(S_AUGASSIGN, start)
        n.a = target
        n.n = op
        n.b = value
        return n

    def parse_if_statement(self) -> Node:
        start = self.node_start()
        self.bump(T_IF)
        test = self.parse_named_expression_or_higher(0)
        self.expect(T_COLON)
        body = self.parse_body("if")
        clauses: list[Node] = []
        saved = self.list_begin(RC_ELIF)
        last = -1
        while self.at(T_ELIF):
            if last == self.token_id:
                raise AssertionError("The parser is no longer progressing")
            last = self.token_id
            clauses.append(self.parse_elif_or_else_clause(True))
        self.recovery_context = saved
        if self.at(T_ELSE):
            clauses.append(self.parse_elif_or_else_clause(False))
        n = self.new(S_IF, start)
        n.a = test
        n.ys = body
        n.xs = clauses
        return n

    def parse_elif_or_else_clause(self, elif_: bool) -> Node:
        start = self.node_start()
        self.bump(T_ELIF if elif_ else T_ELSE)
        test: Node | None = None
        if elif_:
            test = self.parse_named_expression_or_higher(0)
        self.expect(T_COLON)
        body = self.parse_body("elif" if elif_ else "else")
        n = self.new(X_ELIF_ELSE, start)
        n.a = test
        n.ys = body
        return n

    def parse_try_statement(self) -> Node:
        try_start = self.node_start()
        self.bump(T_TRY)
        self.expect(T_COLON)
        is_star = -1
        body = self.parse_body("try")
        has_except = self.at(T_EXCEPT)
        mixed_starts: list[int] = []
        mixed_ends: list[int] = []
        handlers: list[Node] = []
        saved = self.list_begin(RC_EXCEPT)
        last = -1
        while self.at(T_EXCEPT):
            if last == self.token_id:
                raise AssertionError("The parser is no longer progressing")
            last = self.token_id
            handler = self.parse_except_clause()
            star = 1 if handler.flag2 else 0
            if is_star < 0:
                is_star = star
            elif is_star != star:
                mixed_starts.append(handler.start)
                mixed_ends.append(handler.end)
            handlers.append(handler)
        self.recovery_context = saved
        for i in range(len(mixed_starts)):
            self.add_error("Cannot have both 'except' and 'except*' on the same 'try'", mixed_starts[i], mixed_ends[i])
        orelse: list[Node] = EMPTY
        if self.eat(T_ELSE):
            self.expect(T_COLON)
            orelse = self.parse_body("else")
        finalbody: list[Node] = EMPTY
        has_finally = False
        if self.eat(T_FINALLY):
            self.expect(T_COLON)
            finalbody = self.parse_body("finally")
            has_finally = True
        if not has_except and not has_finally:
            self.add_error("Expected `except` or `finally` after `try` block", self.lexer.start, self.lexer.end)
        if has_finally and self.at(T_ELSE):
            self.add_error("`else` block must come before `finally` block", self.lexer.start, self.lexer.end)
        n = self.new(S_TRY, try_start)
        n.ys = body
        n.xs = handlers
        n.zs = orelse
        n.ws = finalbody
        n.flag = is_star == 1
        return n

    def parse_except_clause(self) -> Node:
        start = self.node_start()
        self.bump(T_EXCEPT)
        star = self.eat(T_STAR)
        typ: Node | None = None
        if self.at_expr():
            e = self.parse_expression_list(0)
            if e.kind == E_TUPLE and not e.flag:
                if self.at(T_AS):
                    self.add_error("Multiple exception types must be parenthesized when using `as`", e.start, e.end)
            typ = e
        elif star or self.at(T_AS):
            self.add_error("Expected one or more exception types", self.lexer.start, self.lexer.end)
        h = Node(X_EXCEPT_HANDLER, 0, 0)
        if self.eat(T_AS):
            if self.at_name_or_soft_keyword():
                name = self.parse_identifier(0)
                h.flag = True
                h.s = name.s
                h.nstart = name.start
                h.nend = name.end
            else:
                self.add_error("Expected name after `as`", self.lexer.start, self.lexer.end)
        self.expect(T_COLON)
        body = self.parse_body("except")
        h.a = typ
        h.ys = body
        h.flag2 = star
        h.start = self.range_start(start)
        h.end = self.prev_token_end
        return h

    def parse_for_statement(self, start: int) -> Node:
        self.bump(T_FOR)
        target = self.parse_expression_list(EC_STARRED_CONDITIONAL | EC_EXCLUDE_IN)
        set_expr_ctx(target, CTX_STORE)
        self.validate_assignment_target(target)
        self.expect(T_IN)
        it = self.parse_expression_list(EC_STARRED_BITWISE)
        self.expect(T_COLON)
        body = self.parse_body("for")
        orelse: list[Node] = EMPTY
        if self.eat(T_ELSE):
            self.expect(T_COLON)
            orelse = self.parse_body("else")
        n = self.new(S_FOR, start)
        n.a = target
        n.b = it
        n.ys = body
        n.zs = orelse
        return n

    def parse_while_statement(self) -> Node:
        start = self.node_start()
        self.bump(T_WHILE)
        test = self.parse_named_expression_or_higher(0)
        self.expect(T_COLON)
        body = self.parse_body("while")
        orelse: list[Node] = EMPTY
        if self.eat(T_ELSE):
            self.expect(T_COLON)
            orelse = self.parse_body("else")
        n = self.new(S_WHILE, start)
        n.a = test
        n.ys = body
        n.zs = orelse
        return n

    def parse_function_definition(self, decorators: list[Node], start: int) -> Node:
        self.bump(T_DEF)
        name = self.parse_identifier(0)
        tparams = self.try_parse_type_params()
        params = self.parse_parameters(True)
        returns: Node | None = None
        if self.eat(T_RARROW):
            if self.at_expr():
                r = self.parse_expression_list(0)
                if r.kind == E_TUPLE and not r.flag:
                    self.add_error("Multiple return types must be parenthesized", r.start, r.end)
                returns = r
            else:
                self.add_error("Expected an expression", self.lexer.start, self.lexer.end)
        self.expect(T_COLON)
        body = self.parse_body("def")
        n = self.new(S_FUNCTIONDEF, start)
        n.s = name.s
        n.nstart = name.start
        n.nend = name.end
        n.xs = decorators
        n.a = params
        n.b = returns
        n.c = tparams
        n.ys = body
        return n

    def parse_class_definition(self, decorators: list[Node], start: int) -> Node:
        self.bump(T_CLASS)
        name = self.parse_identifier(0)
        tparams = self.try_parse_type_params()
        arguments: Node | None = None
        if self.at(T_LPAR):
            arguments = self.parse_arguments(True)
        self.expect(T_COLON)
        body = self.parse_body("class")
        n = self.new(S_CLASSDEF, start)
        n.s = name.s
        n.nstart = name.start
        n.nend = name.end
        n.xs = decorators
        n.a = arguments
        n.c = tparams
        n.ys = body
        return n

    def parse_with_statement(self, start: int) -> Node:
        self.bump(T_WITH)
        items = self.parse_with_items()
        self.expect(T_COLON)
        body = self.parse_body("with")
        n = self.new(S_WITH, start)
        n.xs = items
        n.ys = body
        return n

    def parse_with_items(self) -> list[Node]:
        if not self.at_expr():
            self.add_error("Expected the start of an expression after `with` keyword", self.lexer.start, self.lexer.end)
            return []
        if self.at(T_LPAR):
            items = self.try_parse_parenthesized_with_items()
            if items is not None:
                self.expect(T_RPAR)
                return items
            return self.parse_with_item_list(RC_WITH_ITEMS_PAREN_EXPR)
        return self.parse_with_item_list(RC_WITH_ITEMS)

    def parse_with_item_list(self, rc: int) -> list[Node]:
        items: list[Node] = []
        saved = self.list_begin(rc)
        state = [-1, 1, -1, -1, 0]
        while self.sep_step(rc, state) == 1:
            items.append(self.parse_with_item(False))
            self.sep_after(state)
        self.sep_end(rc, state, saved)
        return items

    def try_parse_parenthesized_with_items(self) -> list[Node] | None:
        cp = self.checkpoint()
        parenthesized_kind = True
        self.bump(T_LPAR)
        items: list[Node] = []
        parens: list[bool] = []
        has_optional_vars = False
        saved = self.list_begin(RC_WITH_ITEMS_PAREN)
        state = [-1, 1, -1, -1, 0]
        while self.sep_step(RC_WITH_ITEMS_PAREN, state) == 1:
            item = self.parse_with_item(True)
            if item.b is not None:
                has_optional_vars = True
            items.append(item)
            parens.append(item.flag)
            self.sep_after(state)
        self.sep_end(RC_WITH_ITEMS_PAREN, state, saved)
        if has_optional_vars:
            for i in range(len(items)):
                if parens[i]:
                    continue
                ce = items[i].a
                assert ce is not None
                k = ce.kind
                if k == E_NAMED:
                    self.add_error("Unparenthesized named expression cannot be used here", ce.start, ce.end)
                elif k == E_STARRED:
                    self.add_error("Starred expression cannot be used here", ce.start, ce.end)
                elif k == E_YIELD or k == E_YIELDFROM:
                    self.add_error("Yield expression cannot be used here", ce.start, ce.end)
        elif self.at(T_RPAR) and self.peek() in (T_COLON, T_NEWLINE):
            if len(items) == 0:
                parenthesized_kind = False
            else:
                for i in range(len(items)):
                    ce = items[i].a
                    assert ce is not None
                    k = ce.kind
                    if not parens[i] and (k == E_NAMED or k == E_STARRED or k == E_YIELD or k == E_YIELDFROM):
                        parenthesized_kind = False
        else:
            parenthesized_kind = False
        if parenthesized_kind:
            for item in items:
                item.flag = False
            return items
        self.rewind(cp)
        return None

    def parse_with_item(self, speculative: bool) -> Node:
        # X_WITHITEM; flag: the context expression's is_parenthesized (cleared by the caller)
        start = self.node_start()
        if speculative:
            ce = self.parse_named_expression_or_higher(EC_YIELD_OR_STARRED_BITWISE)
        else:
            ce = self.parse_conditional_expression_or_higher()
        paren = self.pp
        ov: Node | None = None
        if self.at(T_AS):
            self.bump(T_AS)
            t = self.parse_conditional_expression_or_higher_impl(EC_STARRED_CONDITIONAL)
            self.validate_assignment_target(t)
            set_expr_ctx(t, CTX_STORE)
            ov = t
        n = self.new(X_WITHITEM, start)
        n.a = ce
        n.b = ov
        n.flag = paren
        return n

    def classify_match_token(self) -> int:
        # 0 keyword, 1 identifier, 2 keyword or identifier
        first, second = self.peek2()
        if first == T_NOT and second == T_IN:
            return 1
        if first in (T_NAME, T_INT, T_FLOAT, T_COMPLEX, T_STRING, T_FSTRINGSTART, T_TSTRINGSTART,
                     T_LBRACE, T_TILDE, T_ELLIPSIS, T_NOT, T_AWAIT, T_YIELD, T_LAMBDA):
            return 0
        if first in (T_LPAR, T_LSQB, T_STAR, T_PLUS, T_MINUS):
            return 2
        if is_soft_keyword(first) or first == T_TRUE or first == T_FALSE or first == T_NONE:
            return 0
        return 1

    def try_parse_match_statement(self) -> Node | None:
        cp = self.checkpoint()
        start = self.node_start()
        self.bump(T_MATCH)
        subject = self.parse_match_subject_expression()
        k = self.lexer.kind
        if k == T_COLON and self.peek() == T_NEWLINE:
            self.bump(T_COLON)
            cases = self.parse_match_body()
            n = self.new(S_MATCH, start)
            n.a = subject
            n.xs = cases
            return n
        if k == T_NEWLINE:
            first, second = self.peek2()
            if first == T_INDENT and second == T_CASE:
                self.add_error("Expected " + KIND_TEXT[T_COLON] + ", found " + KIND_TEXT[k], self.lexer.start, self.lexer.end)
                cases = self.parse_match_body()
                n = self.new(S_MATCH, start)
                n.a = subject
                n.xs = cases
                return n
        self.rewind(cp)
        return None

    def parse_match_statement(self) -> Node:
        start = self.node_start()
        self.bump(T_MATCH)
        subject = self.parse_match_subject_expression()
        self.expect(T_COLON)
        cases = self.parse_match_body()
        n = self.new(S_MATCH, start)
        n.a = subject
        n.xs = cases
        return n

    def parse_match_subject_expression(self) -> Node:
        start = self.node_start()
        subject = self.parse_named_expression_or_higher(EC_STARRED_BITWISE)
        paren = self.pp
        if self.at(T_COMMA):
            return self.parse_tuple_expression(subject, start, False, 2, EC_STARRED_BITWISE)
        if not paren and subject.kind == E_STARRED:
            self.add_error("Starred expression cannot be used here", subject.start, subject.end)
        return subject

    def parse_match_body(self) -> list[Node]:
        self.expect(T_NEWLINE)
        if not self.eat(T_INDENT):
            self.add_error("Expected an indented block after `match` statement", self.lexer.start, self.lexer.end)
        cases: list[Node] = []
        if not self.at(T_CASE):
            self.add_error("Expected `case` block", self.lexer.start, self.lexer.end)
        else:
            last = -1
            while self.at(T_CASE):
                if last == self.token_id:
                    raise AssertionError("The parser is no longer progressing")
                last = self.token_id
                cases.append(self.parse_match_case())
        self.expect(T_DEDENT)
        return cases

    def parse_match_case(self) -> Node:
        start = self.node_start()
        self.bump(T_CASE)
        pattern = self.parse_match_patterns()
        guard: Node | None = None
        if self.eat(T_IF):
            if self.at_expr():
                guard = self.parse_named_expression_or_higher(0)
            else:
                self.add_error("Expected an expression", self.lexer.start, self.lexer.end)
        self.expect(T_COLON)
        body = self.parse_body("case")
        n = self.new(X_MATCH_CASE, start)
        n.a = pattern
        n.b = guard
        n.ys = body
        return n

    def parse_async_statement(self) -> Node:
        start = self.node_start()
        self.bump(T_ASYNC)
        k = self.lexer.kind
        if k == T_DEF:
            n = self.parse_function_definition(EMPTY, start)
            n.flag = True
            return n
        if k == T_WITH:
            n = self.parse_with_statement(start)
            n.flag = True
            return n
        if k == T_FOR:
            n = self.parse_for_statement(start)
            n.flag = True
            return n
        self.add_error("Expected `def`, `with` or `for` to follow `async`, found " + KIND_TEXT[k],
                       self.lexer.start, self.lexer.end)
        if self.depth_remaining == 0:
            rs = self.range_start(start)
            self.add_error("Source is too deeply nested", rs, self.prev_token_end)
            n = Node(S_EXPR, rs, self.prev_token_end)
            name = Node(E_NAME, rs, self.prev_token_end)
            name.s = b"async"
            name.n = CTX_INVALID
            n.a = name
            return n
        self.depth_remaining -= 1
        stmt = self.parse_statement()
        self.depth_remaining += 1
        return stmt

    def parse_decorators(self) -> Node:
        start = self.node_start()
        decorators: list[Node] = []
        last = -1
        while self.at(T_AT):
            if last == self.token_id:
                raise AssertionError("The parser is no longer progressing")
            last = self.token_id
            dstart = self.node_start()
            self.bump(T_AT)
            if self.at(T_DEF) or self.at(T_CLASS):
                e = self.parse_missing_name()
            else:
                e = self.parse_named_expression_or_higher(0)
            d = self.new(X_DECORATOR, dstart)
            d.a = e
            decorators.append(d)
            self.expect(T_NEWLINE)
        k = self.lexer.kind
        if k == T_DEF:
            return self.parse_function_definition(decorators, start)
        if k == T_CLASS:
            return self.parse_class_definition(decorators, start)
        if k == T_ASYNC and self.peek() == T_DEF:
            self.bump(T_ASYNC)
            n = self.parse_function_definition(decorators, start)
            n.flag = True
            return n
        self.add_error("Expected class, function definition or async function definition after decorator",
                       self.lexer.start, self.lexer.end)
        n = self.new(S_FUNCTIONDEF, start)
        n.xs = decorators
        n.nstart = self.prev_token_end
        n.nend = self.prev_token_end
        n.a = self.missing(P_PARAMETERS)
        return n

    def parse_body(self, clause: str) -> list[Node]:
        nl_start = self.lexer.start
        nl_end = self.lexer.end
        if self.eat(T_NEWLINE):
            if self.at(T_INDENT):
                return self.parse_block()
            if self.lexer.start == self.lexer.end:
                es = nl_start
                ee = nl_end
            else:
                es = self.lexer.start
                ee = self.lexer.end
            self.add_error("Expected an indented block after " + CLAUSE_TEXT[clause], es, ee)
        else:
            if self.at_simple_stmt():
                return self.parse_simple_statements()
            self.add_error("Expected a simple statement", self.lexer.start, self.lexer.end)
        return []

    def parse_block(self) -> list[Node]:
        self.bump(T_INDENT)
        stmts: list[Node] = []
        if self.depth_remaining == 0:
            self.report_recursion_limit_exceeded(self.lexer.start, self.lexer.end)
        else:
            self.depth_remaining -= 1
            saved = self.list_begin(RC_BLOCK_STATEMENTS)
            state = [-1, 0]
            while self.list_step(RC_BLOCK_STATEMENTS, state) == 1:
                stmts.append(self.parse_statement())
            self.recovery_context = saved
            self.depth_remaining += 1
        self.expect(T_DEDENT)
        return stmts

    # ---------------------------------------------------------------- parameters
    def parse_parameter(self, start: int, funcdef: bool, allow_star_annotation: bool) -> Node:
        name = self.parse_identifier(0)
        annotation: Node | None = None
        if funcdef and self.eat(T_COLON):
            if self.at_expr():
                if allow_star_annotation:
                    annotation = self.parse_conditional_expression_or_higher_impl(EC_STARRED_BITWISE)
                else:
                    annotation = self.parse_conditional_expression_or_higher()
            else:
                self.add_error("Expected an expression", self.lexer.start, self.lexer.end)
        n = self.new(P_PARAMETER, start)
        n.s = name.s
        n.nstart = name.start
        n.nend = name.end
        n.a = annotation
        return n

    def parse_parameter_with_default(self, start: int, funcdef: bool) -> Node:
        p = self.parse_parameter(start, funcdef, False)
        default: Node | None = None
        if self.eat(T_EQUAL):
            if self.at_expr():
                default = self.parse_conditional_expression_or_higher()
            else:
                self.add_error("Expected an expression", self.lexer.start, self.lexer.end)
        n = self.new(P_PARAM_DEFAULT, start)
        n.a = p
        n.b = default
        return n

    def parse_parameters(self, funcdef: bool) -> Node:
        start = self.node_start()
        if funcdef:
            self.expect(T_LPAR)
        params = Node(P_PARAMETERS, 0, 0)
        scratch: list[Node] = []
        args_split = -1
        kwonly_split = -1
        seen_default = False
        seen_posonly_sep = False
        seen_kwonly_sep = False
        seen_kwonly_param_after_sep = False
        last_kwonly_sep_start = -1
        last_kwonly_sep_end = -1
        rc = RC_FUNCTION_PARAMETERS if funcdef else RC_LAMBDA_PARAMETERS
        saved = self.list_begin(rc)
        state = [-1, 1, -1, -1, 0]
        while self.sep_step(rc, state) == 1:
            param_start = self.node_start()
            if params.b is not None:
                self.add_error("Parameter cannot follow var-keyword parameter", self.lexer.start, self.lexer.end)
            k = self.lexer.kind
            if k == T_STAR:
                star_start = self.lexer.start
                star_end = self.lexer.end
                self.bump(T_STAR)
                if kwonly_split < 0:
                    kwonly_split = len(scratch)
                if self.at_name_or_soft_keyword():
                    p = self.parse_parameter(param_start, funcdef, True)
                    ps_start = self.range_start(star_start)
                    if self.at(T_EQUAL):
                        self.add_error("Parameter with `*` or `**` cannot have default value", self.lexer.start, self.lexer.end)
                    if seen_kwonly_sep or params.a is not None:
                        self.add_error("Only one '*' parameter allowed", ps_start, self.prev_token_end)
                    if params.a is None:
                        params.a = p
                    last_kwonly_sep_start = -1
                else:
                    if seen_kwonly_sep:
                        self.add_error("Only one '*' separator allowed", star_start, star_end)
                    if params.a is not None:
                        self.add_error("Keyword-only parameter separator not allowed after '*' parameter", star_start, star_end)
                    seen_kwonly_sep = True
                    last_kwonly_sep_start = star_start
                    last_kwonly_sep_end = star_end
            elif k == T_DOUBLESTAR:
                ds_start = self.lexer.start
                self.bump(T_DOUBLESTAR)
                p = self.parse_parameter(param_start, funcdef, False)
                pds_start = self.range_start(ds_start)
                if params.b is not None:
                    self.add_error("Only one '**' parameter allowed", pds_start, self.prev_token_end)
                if self.at(T_EQUAL):
                    self.add_error("Parameter with `*` or `**` cannot have default value", self.lexer.start, self.lexer.end)
                if seen_kwonly_sep and not seen_kwonly_param_after_sep:
                    self.add_error("Expected one or more keyword parameter after `*` separator", pds_start, self.prev_token_end)
                params.b = p
                last_kwonly_sep_start = -1
            elif k == T_SLASH:
                sl_start = self.lexer.start
                sl_end = self.lexer.end
                self.bump(T_SLASH)
                if len(scratch) == 0 and params.a is None and params.b is None:
                    self.add_error("Position-only parameter separator not allowed as first parameter", sl_start, sl_end)
                if seen_posonly_sep:
                    self.add_error("Only one '/' separator allowed", sl_start, sl_end)
                if seen_kwonly_sep or params.a is not None:
                    self.add_error("'/' parameter must appear before '*' parameter", sl_start, sl_end)
                if not seen_posonly_sep:
                    if kwonly_split < 0:
                        args_split = len(scratch)
                    seen_posonly_sep = True
                last_kwonly_sep_start = -1
            elif self.at_name_or_soft_keyword():
                p = self.parse_parameter_with_default(param_start, funcdef)
                if p.b is None and seen_default and not seen_kwonly_sep and params.a is None:
                    self.add_error("Parameter without a default cannot follow a parameter with a default", p.start, p.end)
                if p.b is not None:
                    seen_default = True
                if seen_kwonly_sep:
                    seen_kwonly_param_after_sep = True
                scratch.append(p)
                last_kwonly_sep_start = -1
            else:
                raise AssertionError("Expected Name, '*', '**', or '/'")
            self.sep_after(state)
        self.sep_end(rc, state, saved)
        if last_kwonly_sep_start >= 0:
            self.add_error("Expected one or more keyword parameter after `*` separator", last_kwonly_sep_start, last_kwonly_sep_end)
        if funcdef:
            self.expect(T_RPAR)
        end = len(scratch)
        if kwonly_split >= 0:
            params.zs = scratch[kwonly_split:]
            end = kwonly_split
        if args_split >= 0:
            params.ys = scratch[args_split:end]
            params.xs = scratch[:args_split]
        elif seen_posonly_sep:
            params.xs = scratch[:end]
        else:
            params.ys = scratch[:end]
        params.start = self.range_start(start)
        params.end = self.prev_token_end
        return params

    def try_parse_type_params(self) -> Node | None:
        if self.at(T_LSQB):
            return self.parse_type_params()
        return None

    def parse_type_params(self) -> Node:
        start = self.node_start()
        self.bump(T_LSQB)
        tps: list[Node] = []
        saved = self.list_begin(RC_TYPE_PARAMS)
        state = [-1, 1, -1, -1, 0]
        while self.sep_step(RC_TYPE_PARAMS, state) == 1:
            tps.append(self.parse_type_param())
            self.sep_after(state)
        self.sep_end(RC_TYPE_PARAMS, state, saved)
        if len(tps) == 0:
            self.add_error("Type parameter list cannot be empty", self.lexer.start, self.lexer.end)
        self.expect(T_RSQB)
        n = self.new(P_TYPE_PARAMS, start)
        n.xs = tps
        return n

    def parse_type_param(self) -> Node:
        start = self.node_start()
        if self.eat(T_STAR):
            name = self.parse_identifier(0)
            default: Node | None = None
            if self.eat(T_EQUAL):
                if self.at_expr():
                    default = self.parse_conditional_expression_or_higher_impl(EC_STARRED_BITWISE)
                else:
                    self.add_error("Expected an expression", self.lexer.start, self.lexer.end)
            n = self.new(P_TYPEVARTUPLE, start)
            n.s = name.s
            n.b = default
            return n
        if self.eat(T_DOUBLESTAR):
            name = self.parse_identifier(0)
            default = None
            if self.eat(T_EQUAL):
                if self.at_expr():
                    default = self.parse_conditional_expression_or_higher()
                else:
                    self.add_error("Expected an expression", self.lexer.start, self.lexer.end)
            n = self.new(P_PARAMSPEC, start)
            n.s = name.s
            n.b = default
            return n
        name = self.parse_identifier(0)
        bound: Node | None = None
        if self.eat(T_COLON):
            if self.at_expr():
                bound = self.parse_conditional_expression_or_higher()
            else:
                self.add_error("Expected an expression", self.lexer.start, self.lexer.end)
        default = None
        if self.eat(T_EQUAL):
            if self.at_expr():
                default = self.parse_conditional_expression_or_higher()
            else:
                self.add_error("Expected an expression", self.lexer.start, self.lexer.end)
        n = self.new(P_TYPEVAR, start)
        n.s = name.s
        n.a = bound
        n.b = default
        return n

    # ---------------------------------------------------------------- validation
    def validate_assignment_target(self, e: Node) -> None:
        k = e.kind
        if k == E_STARRED:
            v = e.a
            assert v is not None
            self.validate_assignment_target(v)
        elif k == E_LIST or k == E_TUPLE:
            for x in e.xs:
                self.validate_assignment_target(x)
        elif k == E_NAME or k == E_ATTRIBUTE or k == E_SUBSCRIPT:
            pass
        else:
            self.add_error("Invalid assignment target", e.start, e.end)

    def validate_annotated_assignment_target(self, e: Node) -> None:
        k = e.kind
        if k == E_LIST:
            self.add_error("Only single target (not list) can be annotated", e.start, e.end)
        elif k == E_TUPLE:
            self.add_error("Only single target (not tuple) can be annotated", e.start, e.end)
        elif k == E_NAME or k == E_ATTRIBUTE or k == E_SUBSCRIPT:
            pass
        else:
            self.add_error("Invalid annotated assignment target", e.start, e.end)

    def validate_delete_target(self, e: Node) -> None:
        k = e.kind
        if k == E_LIST or k == E_TUPLE:
            for x in e.xs:
                self.validate_delete_target(x)
        elif k == E_NAME or k == E_ATTRIBUTE or k == E_SUBSCRIPT:
            pass
        else:
            self.add_error("Invalid delete target", e.start, e.end)

    # ---------------------------------------------------------------- patterns
    def parse_match_patterns(self) -> Node:
        start = self.node_start()
        pattern = self.parse_match_pattern(True)
        if self.at(T_COMMA):
            return self.parse_sequence_match_pattern(pattern, start, 0)
        if pattern.kind == M_STAR:
            self.add_error("Star pattern cannot be used here", pattern.start, pattern.end)
        return pattern

    def parse_match_pattern(self, allow_star: bool) -> Node:
        if self.depth_remaining == 0:
            s = self.prev_token_end
            self.report_recursion_limit_exceeded(self.lexer.start, self.lexer.end)
            inv = Node(E_NAME, s, s)
            inv.n = CTX_INVALID
            mv = Node(M_VALUE, s, s)
            mv.a = inv
            return mv
        self.depth_remaining -= 1
        r = self.parse_match_pattern_inner(allow_star)
        self.depth_remaining += 1
        return r

    def parse_match_pattern_inner(self, allow_star: bool) -> Node:
        start = self.node_start()
        lhs = self.parse_match_pattern_lhs(allow_star)
        if self.at(T_VBAR):
            if lhs.kind == M_STAR:
                self.add_error("Star pattern cannot be used here", lhs.start, lhs.end)
            patterns = [lhs]
            last = -1
            while self.eat(T_VBAR):
                if last == self.token_id:
                    raise AssertionError("The parser is no longer progressing")
                last = self.token_id
                patterns.append(self.parse_match_pattern_lhs(False))
            lhs = self.new(M_OR, start)
            lhs.xs = patterns
        if self.eat(T_AS):
            if lhs.kind == M_STAR:
                self.add_error("Star pattern cannot be used here", lhs.start, lhs.end)
            ident = self.parse_match_pattern_target()
            m = self.new(M_AS, start)
            m.flag = True
            m.s = ident.s
            m.nstart = ident.start
            m.nend = ident.end
            m.a = lhs
            lhs = m
        return lhs

    def parse_match_pattern_lhs(self, allow_star: bool) -> Node:
        start = self.node_start()
        k = self.lexer.kind
        if k == T_LBRACE:
            lhs = self.parse_match_pattern_mapping()
        elif k == T_STAR:
            lhs = self.parse_match_pattern_star()
            if not allow_star:
                self.add_error("Star pattern cannot be used here", lhs.start, lhs.end)
        elif k == T_LPAR or k == T_LSQB:
            lhs = self.parse_parenthesized_or_sequence_pattern()
        else:
            lhs = self.parse_match_pattern_literal()
        if self.at(T_LPAR):
            lhs = self.parse_match_pattern_class(lhs, start)
        if self.at(T_PLUS) or self.at(T_MINUS):
            lhs = self.parse_complex_literal_pattern(lhs, start)
        return lhs

    def parse_match_pattern_mapping(self) -> Node:
        start = self.node_start()
        self.bump(T_LBRACE)
        keys: list[Node] = []
        patterns: list[Node] = []
        rest: Node | None = None
        saved = self.list_begin(RC_MATCH_PATTERN_MAPPING)
        state = [-1, 1, -1, -1, 0]
        while self.sep_step(RC_MATCH_PATTERN_MAPPING, state) == 1:
            item_start = self.node_start()
            if self.eat(T_DOUBLESTAR):
                ident = self.parse_match_pattern_target()
                if rest is not None:
                    self.add_error("Only one double star pattern is allowed", self.range_start(item_start), self.prev_token_end)
                rest = ident
            else:
                p = self.parse_match_pattern_lhs(False)
                if p.kind == M_VALUE:
                    key = p.a
                    assert key is not None
                elif p.kind == M_SINGLETON:
                    if p.n == 0:
                        key = Node(E_NONE, p.start, p.end)
                    else:
                        key = Node(E_BOOL, p.start, p.end)
                        key.flag = p.n == 1
                else:
                    self.add_error("Invalid mapping pattern key", p.start, p.end)
                    key = pattern_to_expr(p)
                keys.append(key)
                self.expect(T_COLON)
                patterns.append(self.parse_match_pattern(False))
                if rest is not None:
                    self.add_error("Pattern cannot follow a double star pattern", self.range_start(item_start), self.prev_token_end)
            self.sep_after(state)
        self.sep_end(RC_MATCH_PATTERN_MAPPING, state, saved)
        self.expect(T_RBRACE)
        n = self.new(M_MAPPING, start)
        n.xs = keys
        n.ys = patterns
        if rest is not None:
            n.flag = True
            n.s = rest.s
            n.nstart = rest.start
            n.nend = rest.end
        return n

    def parse_match_pattern_star(self) -> Node:
        start = self.node_start()
        self.bump(T_STAR)
        ident = self.parse_identifier(0)
        n = self.new(M_STAR, start)
        if not (len(ident.s) > 0 and ident.s == b"_"):
            n.flag = True
            n.s = ident.s
            n.nstart = ident.start
            n.nend = ident.end
        return n

    def parse_match_pattern_target(self) -> Node:
        ident = self.parse_identifier(0)
        if ident.s == b"_":
            self.add_error("cannot use '_' as a target", ident.start, ident.end)
        return ident

    def parse_parenthesized_or_sequence_pattern(self) -> Node:
        start = self.node_start()
        if self.eat(T_LPAR):
            close = T_RPAR
        else:
            self.bump(T_LSQB)
            close = T_RSQB
        if self.at(T_NEWLINE) or self.at(T_COLON):
            self.add_error("Missing '" + ("]" if close == T_RSQB else ")") + "'", self.lexer.start, self.lexer.end)
        if self.eat(close):
            return self.new(M_SEQUENCE, start)
        pattern = self.parse_match_pattern(True)
        if close == T_RSQB or self.at(T_COMMA):
            return self.parse_sequence_match_pattern(pattern, start, close)
        self.expect(close)
        return pattern

    def parse_sequence_match_pattern(self, first: Node, start: int, close: int) -> Node:
        # close: the closing token of the brackets, 0 for none
        if close != 0 and (self.at(close) or self.peek() == close):
            self.eat(T_COMMA)
        else:
            self.expect(T_COMMA)
        patterns = [first]
        if close == 0:
            rc = RC_SEQUENCE_MATCH_PATTERN
        elif close == T_RSQB:
            rc = RC_SEQUENCE_MATCH_PATTERN_LIST
        else:
            rc = RC_SEQUENCE_MATCH_PATTERN_TUPLE
        saved = self.list_begin(rc)
        state = [-1, 1, -1, -1, 0]
        while self.sep_step(rc, state) == 1:
            patterns.append(self.parse_match_pattern(True))
            self.sep_after(state)
        self.sep_end(rc, state, saved)
        if close != 0:
            self.expect(close)
        n = self.new(M_SEQUENCE, start)
        n.xs = patterns
        return n

    def parse_match_pattern_literal(self) -> Node:
        start = self.node_start()
        k = self.lexer.kind
        if k == T_NONE or k == T_TRUE or k == T_FALSE:
            self.bump(k)
            n = self.new(M_SINGLETON, start)
            n.n = 0 if k == T_NONE else (1 if k == T_TRUE else 2)
            return n
        if k == T_STRING or k == T_FSTRINGSTART or k == T_TSTRINGSTART:
            s = self.parse_strings()
            n = self.new(M_VALUE, start)
            n.a = s
            return n
        if k == T_COMPLEX or k == T_INT or k == T_FLOAT:
            if k == T_INT:
                text = self.cur_text()
                self.bump(T_INT)
                v = self.new(E_INT, start)
                set_int_value(v, text)
            else:
                text = strip_underscores(self.cur_text())
                self.bump(k)
                if k == T_COMPLEX:
                    v = self.new(E_COMPLEX, start)
                    v.fval = float(text[:len(text) - 1].decode())
                else:
                    v = self.new(E_FLOAT, start)
                    v.fval = float(text.decode())
            n = Node(M_VALUE, v.start, v.end)
            n.a = v
            return n
        if k == T_PLUS or k == T_MINUS:
            nk = self.peek()
            if nk == T_INT or nk == T_FLOAT or nk == T_COMPLEX:
                u = self.parse_unary_expression(2 if k == T_PLUS else 3, 0)
                if u.n == 2:
                    self.add_error("Unary '+' is not allowed as a literal pattern", u.start, u.end)
                n = self.new(M_VALUE, start)
                n.a = u
                return n
        if self.at_name_or_keyword():
            if self.peek() == T_DOT:
                ident = self.parse_name(0)
                attr = ident
                while self.lexer.kind == T_DOT:
                    attr = self.parse_attribute_expression(attr, start, 0)
                n = self.new(M_VALUE, start)
                n.a = attr
                return n
            ident = self.parse_identifier(0)
            n = Node(M_AS, ident.start, ident.end)
            if ident.s != b"_":
                n.flag = True
                n.s = ident.s
                n.nstart = ident.start
                n.nend = ident.end
            return n
        self.add_error("Expected a pattern", self.lexer.start, self.lexer.end)
        inv = self.missing(E_NAME)
        inv.n = CTX_INVALID
        n = Node(M_VALUE, inv.start, inv.end)
        n.a = inv
        return n

    def parse_complex_literal_pattern(self, lhs: Node, start: int) -> Node:
        if self.eat(T_PLUS):
            op = 0
        else:
            self.bump(T_MINUS)
            op = 1
        if lhs.kind == M_VALUE:
            lv = lhs.a
            assert lv is not None
            if not is_real_number(lv):
                self.add_error("Expected a real number in complex literal pattern", lhs.start, lhs.end)
        else:
            self.add_error("Expected a real number in complex literal pattern", lhs.start, lhs.end)
            lv = pattern_to_expr(lhs)
        rp = self.parse_match_pattern_lhs(False)
        if rp.kind == M_VALUE:
            rv = rp.a
            assert rv is not None
            if rv.kind != E_COMPLEX:
                self.add_error("Expected an imaginary number in complex literal pattern", rp.start, rp.end)
        else:
            self.add_error("Expected an imaginary number in complex literal pattern", rp.start, rp.end)
            rv = pattern_to_expr(rp)
        rs = self.range_start(start)
        b = Node(E_BINOP, rs, self.prev_token_end)
        b.a = lv
        b.n = op
        b.b = rv
        n = Node(M_VALUE, rs, self.prev_token_end)
        n.a = b
        return n

    def parse_match_pattern_class(self, cls: Node, start: int) -> Node:
        if cls.kind == M_AS and cls.a is None and cls.flag:
            c = Node(E_NAME, cls.nstart, cls.nend)
            if len(cls.s) > 0:
                c.s = cls.s
            else:
                c.n = CTX_INVALID
        elif cls.kind == M_VALUE and cls.a is not None and cls.a.kind == E_ATTRIBUTE:
            c = cls.a
        else:
            self.add_error("Invalid value for a class pattern", cls.start, cls.end)
            c = pattern_to_expr(cls)
        self.bump(T_LPAR)
        patterns: list[Node] = []
        keywords: list[Node] = []
        seen_pattern = False
        seen_keyword = False
        saved = self.list_begin(RC_MATCH_PATTERN_CLASS_ARGUMENTS)
        state = [-1, 1, -1, -1, 0]
        while self.sep_step(RC_MATCH_PATTERN_CLASS_ARGUMENTS, state) == 1:
            pstart = self.node_start()
            p = self.parse_match_pattern(False)
            if self.eat(T_EQUAL):
                seen_pattern = False
                seen_keyword = True
                kw = Node(X_PATTERN_KEYWORD, 0, 0)
                if p.kind == M_AS and p.a is None and p.flag:
                    kw.s = p.s
                    kw.nstart = p.nstart
                    kw.nend = p.nend
                else:
                    self.add_error("Expected an identifier for the keyword pattern", p.start, p.end)
                    kw.nstart = self.prev_token_end
                    kw.nend = self.prev_token_end
                kw.a = self.parse_match_pattern(False)
                kw.start = self.range_start(pstart)
                kw.end = self.prev_token_end
                keywords.append(kw)
            else:
                seen_pattern = True
                patterns.append(p)
            if seen_keyword and seen_pattern:
                self.add_error("Positional patterns cannot follow keyword patterns", self.range_start(pstart), self.prev_token_end)
            self.sep_after(state)
        self.sep_end(RC_MATCH_PATTERN_CLASS_ARGUMENTS, state, saved)
        self.expect(T_RPAR)
        n = self.new(M_CLASS, start)
        n.a = c
        n.xs = patterns
        n.ys = keywords
        return n


# The identifier characters whose NFKC (unicode-normalization 0.1.25, Unicode 16 and 17) differs
# from CPython 3.13's (Unicode 15.1): compatibility decompositions of characters added since
NFKC_EXTRA: dict[str, str] = {
    "\ua7f1": "S", "\U0001ccf0": "0", "\U0001ccf1": "1", "\U0001ccf2": "2", "\U0001ccf3": "3",
    "\U0001ccf4": "4", "\U0001ccf5": "5", "\U0001ccf6": "6", "\U0001ccf7": "7", "\U0001ccf8": "8",
    "\U0001ccf9": "9",
}


def nfkc(name: bytes) -> bytes:
    text = name.decode()
    if name.find(b"\xea\x9f\xb1") >= 0 or name.find(b"\xf0\x9c\xb3") >= 0:
        out: list[str] = []
        for ch in text:
            out.append(NFKC_EXTRA.get(ch, ch))
        text = "".join(out)
    return unicodedata.normalize("NFKC", text).encode()


class ParserCheckpoint:
    def __init__(self, lexer: LexerCheckpoint, ntokens: int, nerrors: int, token_id: int,
                 prev_token_end: int, recovery_context: int) -> None:
        self.lexer: LexerCheckpoint = lexer
        self.ntokens: int = ntokens
        self.nerrors: int = nerrors
        self.token_id: int = token_id
        self.prev_token_end: int = prev_token_end
        self.recovery_context: int = recovery_context


def set_expr_ctx(e: Node, ctx: int) -> None:
    k = e.kind
    if k == E_NAME or k == E_ATTRIBUTE or k == E_SUBSCRIPT:
        e.n = ctx
    elif k == E_STARRED:
        e.n = ctx
        v = e.a
        assert v is not None
        set_expr_ctx(v, ctx)
    elif k == E_UNARYOP:
        v = e.a
        assert v is not None
        set_expr_ctx(v, ctx)
    elif k == E_LIST or k == E_TUPLE:
        e.n = ctx
        for x in e.xs:
            set_expr_ctx(x, ctx)


def string_expr(part: Node) -> Node:
    # a single string literal, bytes literal, f-string or t-string as an expression
    k = part.kind
    if k == X_STRING_PART:
        n = Node(E_STRING, part.start, part.end)
    elif k == X_BYTES_PART:
        n = Node(E_BYTES, part.start, part.end)
    elif part.n & F_TSTRING:
        n = Node(E_TSTRING, part.start, part.end)
    else:
        n = Node(E_FSTRING, part.start, part.end)
    n.xs = [part]
    return n


def invalid_string_part(part: Node) -> Node:
    n = Node(X_STRING_PART, part.start, part.end)
    n.flag2 = True
    return n


def strip_underscores(text: bytes) -> bytes:
    if text.find(b"_") < 0:
        return text
    return text.replace(b"_", b"")


U64_MAX_DIGITS = b"18446744073709551615"
I64_MAX = 9223372036854775807


def set_int_value(n: Node, text: bytes) -> None:
    """Ruff's Int of an integer literal's text: n.flag2 (Small) when it fits a u64, n.flag when it
    fits an i64 (then n.ival), and n.s its display (the u64's digits, or the text of a Big: the
    digits without underscores, or the whole token of a radix literal)."""
    t1 = text[1:2] if len(text) > 1 else b""
    if text[:1] == b"0" and t1 != b"" and t1 in b"xXoObB":
        digits = strip_underscores(text[2:])
        radix = 16 if t1 in b"xX" else (8 if t1 in b"oO" else 2)
        bits = 4 if radix == 16 else (3 if radix == 8 else 1)
        i = 0
        while i < len(digits) - 1 and digits[i] == 48:
            i += 1
        digits = digits[i:]
        # bits needed: the leading digit's bits plus the rest
        lead = int(digits[:1].decode(), radix)
        lead_bits = 0
        while lead > 0:
            lead_bits += 1
            lead >>= 1
        nbits = lead_bits + bits * (len(digits) - 1)
        if nbits > 64:
            n.s = text
            return
        n.flag2 = True
        if nbits <= 63:
            n.flag = True
            n.ival = int(digits.decode(), radix)
            n.s = str(n.ival).encode()
            return
        # 2**63 to 2**64 - 1: the decimal digits of a u64
        hi = int(digits[:len(digits) - 4].decode() if len(digits) > 4 else "0", radix)
        lo_digits = digits[len(digits) - 4:] if len(digits) > 4 else digits
        lo = int(lo_digits.decode(), radix)
        lo_bits = bits * len(lo_digits)
        n.s = u64_decimal(hi, lo, lo_bits)
        return
    digits = strip_underscores(text)
    i = 0
    while i < len(digits) - 1 and digits[i] == 48:
        i += 1
    d = digits[i:]
    if len(d) > 20 or (len(d) == 20 and d > U64_MAX_DIGITS):
        n.s = digits
        return
    n.flag2 = True
    if len(d) < 19 or (len(d) == 19 and d <= b"9223372036854775807"):
        n.flag = True
        n.ival = int(d.decode())
    n.s = d


def u64_decimal(hi: int, lo: int, lo_bits: int) -> bytes:
    # the decimal digits of hi * 2**lo_bits + lo, a value of 2**63 or more that fits a u64 (hi < 2**63)
    digits = [int(c) for c in str(hi)]
    for _ in range(lo_bits):
        carry = 0
        for j in range(len(digits) - 1, -1, -1):
            v = digits[j] * 2 + carry
            digits[j] = v % 10
            carry = v // 10
        if carry:
            digits.insert(0, carry)
    carry = lo
    j = len(digits) - 1
    while carry > 0 or j >= 0:
        if j < 0:
            digits.insert(0, 0)
            j = 0
        v = digits[j] + carry
        digits[j] = v % 10
        carry = v // 10
        j -= 1
    k = 0
    while k < len(digits) - 1 and digits[k] == 0:
        k += 1
    return "".join([str(x) for x in digits[k:]]).encode()


def debug_str(s: bytes) -> str:
    # Rust's {:?} of a str
    out = ['"']
    for ch in s.decode():
        o = ord(ch)
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif o < 32 or o == 127:
            out.append("\\u{" + hex(o)[2:] + "}")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def is_real_number(e: Node) -> bool:
    if e.kind == E_INT or e.kind == E_FLOAT:
        return True
    if e.kind == E_UNARYOP and (e.n == 2 or e.n == 3):
        v = e.a
        assert v is not None
        return is_real_number(v)
    return False


def pattern_to_expr(p: Node) -> Node:
    # recovery::pattern_to_expr
    k = p.kind
    if k == M_SINGLETON:
        if p.n == 0:
            return Node(E_NONE, p.start, p.end)
        b = Node(E_BOOL, p.start, p.end)
        b.flag = p.n == 1
        return b
    if k == M_VALUE:
        v = p.a
        assert v is not None
        return v
    if k == M_SEQUENCE:
        lst = Node(E_LIST, p.start, p.end)
        lst.xs = [pattern_to_expr(x) for x in p.xs]
        lst.n = CTX_STORE
        return lst
    if k == M_MAPPING:
        items: list[Node] = []
        for i in range(len(p.xs)):
            it = Node(X_DICT_ITEM, 0, 0)
            it.a = p.xs[i]
            it.b = pattern_to_expr(p.ys[i])
            items.append(it)
        if p.flag:
            it = Node(X_DICT_ITEM, 0, 0)
            nm = Node(E_NAME, p.nstart, p.nend)
            nm.s = p.s
            nm.n = CTX_STORE
            it.b = nm
            items.append(it)
        d = Node(E_DICT, p.start, p.end)
        d.xs = items
        return d
    if k == M_CLASS:
        args = Node(X_ARGUMENTS, p.start, p.end)
        args.xs = [pattern_to_expr(x) for x in p.xs]
        kws: list[Node] = []
        for kp in p.ys:
            kw = Node(X_KEYWORD, kp.start, kp.end)
            kw.flag = True
            kw.s = kp.s
            kw.nstart = kp.nstart
            kw.nend = kp.nend
            v = kp.a
            assert v is not None
            kw.a = pattern_to_expr(v)
            kws.append(kw)
        args.ys = kws
        c = Node(E_CALL, p.start, p.end)
        c.a = p.a
        c.b = args
        return c
    if k == M_STAR:
        st = Node(E_STARRED, p.start, p.end)
        st.n = CTX_STORE
        if p.flag:
            nm = Node(E_NAME, p.nstart, p.nend)
            nm.s = p.s
        else:
            nm = Node(E_NAME, p.end - 1, p.end)
            nm.s = b"_"
        nm.n = CTX_STORE
        st.a = nm
        return st
    if k == M_AS:
        if p.a is not None and p.flag:
            nm = Node(E_NAME, p.start, p.end)
            nm.n = CTX_INVALID
            return nm
        if p.a is not None:
            return pattern_to_expr(p.a)
        if p.flag:
            nm = Node(E_NAME, p.nstart, p.nend)
            nm.s = p.s
            nm.n = CTX_STORE
            return nm
        nm = Node(E_NAME, p.start, p.end)
        nm.s = b"_"
        nm.n = CTX_STORE
        return nm
    # an or-pattern: a | b | c, left to right, ranged by the patterns
    first = p.xs[0]
    left = pattern_to_expr(first)
    start = first.start
    for x in p.xs[1:]:
        right = pattern_to_expr(x)
        b = Node(E_BINOP, start, x.end)
        b.a = left
        b.n = 9
        b.b = right
        left = b
    return left


HEX_DIGITS = b"0123456789abcdefABCDEF"


class StringParser:
    """string.rs's StringParser over src[start:end], the text between a string's quotes (or an
    f-string middle's text); err_msg is set (with its range) if an escape is invalid."""

    def __init__(self, src: bytes, start: int, end: int, flags: int) -> None:
        self.src: bytes = src
        self.start: int = start
        self.end: int = end
        self.pos: int = start
        self.flags: int = flags
        self.err_msg = ""
        self.err_start = 0
        self.err_end = 0

    def error(self, msg: str, start: int, end: int) -> None:
        self.err_msg = msg
        self.err_start = start
        self.err_end = end

    def parse_unicode_literal(self, count: int) -> int:
        # -1 on an error
        p = 0
        for _ in range(count):
            start = self.pos
            if self.pos >= self.end:
                self.error("Got unexpected unicode", self.pos, self.pos)
                return -1
            c = self.src[self.pos]
            if c < 0x80 and HEX_DIGITS.find(bytes([c])) >= 0:
                self.pos += 1
                p = p * 16 + int(chr(c), 16)
            else:
                w = 1 if c < 0x80 else (2 if c < 0xE0 else (3 if c < 0xF0 else 4))
                self.error("Got unexpected unicode", start, start + w)
                return -1
        if 0xD800 <= p <= 0xDFFF:
            return 0xFFFD
        if p > 0x10FFFF:
            self.error("Got unexpected unicode", self.pos, self.pos)
            return -1
        return p

    def parse_octet(self, o: int) -> int:
        value = o - 48
        n = 1
        while n < 3 and self.pos < self.end and 48 <= self.src[self.pos] <= 55:
            value = value * 8 + self.src[self.pos] - 48
            self.pos += 1
            n += 1
        return value

    def parse_unicode_name(self) -> int:
        start_pos = self.pos
        if self.pos >= self.end or self.src[self.pos] != 123:
            # (the character is consumed even when it is not a brace)
            if self.pos < self.end:
                c = self.src[self.pos]
                self.pos += 1 if c < 0x80 else (2 if c < 0xE0 else (3 if c < 0xF0 else 4))
            self.error("Missing `{` in Unicode escape sequence", start_pos, start_pos)
            return -1
        self.pos += 1
        name_start = self.pos
        close = self.src.find(b"}", self.pos, self.end)
        if close < 0:
            self.error("Missing `}` in Unicode escape sequence", self.end, self.end)
            return -1
        name = self.src[name_start:close].decode()
        self.pos = close + 1
        cp = lookup_unicode_name(name)
        if cp < 0:
            self.error("Got unexpected unicode", name_start, close)
            return -1
        return cp

    def parse_escaped_char(self, out: list[bytes], is_bytes: bool) -> bool:
        # appends the escape's value (False on an error)
        if self.pos >= self.end:
            self.error("Got unexpected string", self.pos, self.pos)
            return False
        c = self.src[self.pos]
        if c >= 0x80:
            w = 2 if c < 0xE0 else (3 if c < 0xF0 else 4)
            out.append(b"\\" + self.src[self.pos:self.pos + w])
            self.pos += w
            return True
        self.pos += 1
        cp = -2
        if c == 92:
            cp = 92
        elif c == 39:
            cp = 39
        elif c == 34:
            cp = 34
        elif c == 97:
            cp = 7
        elif c == 98:
            cp = 8
        elif c == 102:
            cp = 12
        elif c == 110:
            cp = 10
        elif c == 114:
            cp = 13
        elif c == 116:
            cp = 9
        elif c == 118:
            cp = 11
        elif 48 <= c <= 55:
            cp = self.parse_octet(c)
        elif c == 120:
            cp = self.parse_unicode_literal(2)
            if cp < 0:
                return False
        elif c == 117 and not is_bytes:
            cp = self.parse_unicode_literal(4)
            if cp < 0:
                return False
        elif c == 85 and not is_bytes:
            cp = self.parse_unicode_literal(8)
            if cp < 0:
                return False
        elif c == 78 and not is_bytes:
            cp = self.parse_unicode_name()
            if cp < 0:
                return False
        elif c == 10:
            return True
        elif c == 13:
            if self.pos < self.end and self.src[self.pos] == 10:
                self.pos += 1
            return True
        else:
            out.append(bytes([92, c]))
            return True
        if is_bytes:
            out.append(bytes([cp & 255]))
        else:
            out.append(chr(cp).encode())
        return True

    def parse_string(self) -> bytes:
        src = self.src
        if self.flags & F_RAW:
            return src[self.start:self.end]
        esc = src.find(b"\\", self.start, self.end)
        if esc < 0:
            return src[self.start:self.end]
        out: list[bytes] = []
        while True:
            out.append(src[self.pos:esc])
            self.pos = esc + 1
            if not self.parse_escaped_char(out, False):
                return b""
            esc = src.find(b"\\", self.pos, self.end)
            if esc < 0:
                out.append(src[self.pos:self.end])
                break
        return b"".join(out)

    def parse_bytes(self) -> bytes:
        src = self.src
        for i in range(self.start, self.end):
            if src[i] >= 0x80:
                c = src[i]
                w = 2 if c < 0xE0 else (3 if c < 0xF0 else 4)
                # (Ruff takes the position of the first non-ASCII byte as a character index)
                k = self.char_index_position(i - self.start)
                self.error("bytes can only contain ASCII literal characters", k, k + w)
                return b""
        if self.flags & F_RAW:
            return src[self.start:self.end]
        esc = src.find(b"\\", self.start, self.end)
        if esc < 0:
            return src[self.start:self.end]
        out: list[bytes] = []
        while True:
            out.append(src[self.pos:esc])
            self.pos = esc + 1
            if not self.parse_escaped_char(out, True):
                return b""
            esc = src.find(b"\\", self.pos, self.end)
            if esc < 0:
                out.append(src[self.pos:self.end])
                break
        return b"".join(out)

    def char_index_position(self, index: int) -> int:
        # compute_position(index) (Ruff passes the byte index of the first non-ASCII byte)
        return self.start + index

    def parse_fstring_middle(self) -> bytes:
        src = self.src
        raw = self.flags & F_RAW != 0
        i = self.find3(self.start)
        if i < 0:
            return src[self.start:self.end]
        out: list[bytes] = []
        while True:
            out.append(src[self.pos:i])
            self.pos = i + 1
            c = src[i]
            if c == 123 or c == 125:
                if self.pos < self.end and src[self.pos] == c:
                    self.pos += 1
                out.append(bytes([c]))
            else:
                if not raw and self.pos < self.end:
                    nc = src[self.pos]
                    if (nc == 123 or nc == 125) and self.pos + 1 < self.end and src[self.pos + 1] == nc:
                        out.append(b"\\")
                    elif not self.parse_escaped_char(out, False):
                        return b""
                else:
                    out.append(b"\\")
            i = self.find3(self.pos)
            if i < 0:
                out.append(src[self.pos:self.end])
                break
        return b"".join(out)

    def find3(self, p: int) -> int:
        src = self.src
        while p < self.end:
            c = src[p]
            if c == 123 or c == 125 or c == 92:
                return p
            p += 1
        return -1


def ascii_upper(s: str) -> str:
    out: list[str] = []
    for ch in s:
        out.append(chr(ord(ch) - 32) if "a" <= ch <= "z" else ch)
    return "".join(out)


def is_hex(s: str) -> bool:
    for ch in s:
        if not ("0" <= ch <= "9" or "A" <= ch <= "F"):
            return False
    return len(s) > 0


def lookup_unicode_name(name: str) -> int:
    """The character of a \\N{...} escape, as unicode_names2 1.3.0 (Unicode 16.0) finds it for the
    extension: CPython's unicodedata.lookup() (Unicode 15.1), less named sequences and the TANGUT
    IDEOGRAPH-XXXX names, which unicode_names2 lacks, and with a five-digit CJK UNIFIED
    IDEOGRAPH-0XXXX, the EGYPTIAN HIEROGLYPH-XXXXX names of 13460 to 143FA and the other names and
    aliases added in 16.0 (_names16); -1 for none."""
    up = ascii_upper(name)
    if up.startswith("TANGUT IDEOGRAPH-"):
        return -1
    if up.startswith("EGYPTIAN HIEROGLYPH-"):
        digits = up[20:]
        if len(digits) == 5 and is_hex(digits):
            v = int(digits, 16)
            if 0x13460 <= v <= 0x143FA:
                return v
    if up.startswith("CJK UNIFIED IDEOGRAPH-0") and len(up) == 27:
        name = up[:22] + up[23:]
    try:
        found = unicodedata.lookup(name)
    except KeyError:
        return names16_lookup(up)
    if len(found) != 1:
        return -1
    return ord(found)
