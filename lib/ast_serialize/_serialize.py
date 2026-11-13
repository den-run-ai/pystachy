"""The serializer: ast_serialize 0.13.1's src/serialize_ast.rs (with reachability.rs,
type_comment.rs, mypy_inline_config.rs and func_effect_visitor.rs; MIT, see THIRD_PARTY_NOTICES),
writing mypy's binary AST format from _ast.Node trees.
"""
import struct

from ._ast import (
    CTX_STORE, E_ATTRIBUTE, E_AWAIT, E_BINOP, E_BOOL, E_BOOLOP, E_BYTES, E_CALL, E_COMPARE,
    E_COMPLEX, E_DICT, E_DICTCOMP, E_ELLIPSIS, E_FLOAT, E_FSTRING, E_GENERATOR, E_IF, E_INT,
    E_LAMBDA, E_LIST, E_LISTCOMP, E_NAME, E_NAMED, E_NONE, E_SET, E_SETCOMP, E_SLICE,
    E_STARRED, E_STRING, E_SUBSCRIPT, E_TSTRING, E_TUPLE, E_UNARYOP, E_YIELD, E_YIELDFROM,
    M_AS, M_CLASS, M_MAPPING, M_OR, M_SEQUENCE, M_SINGLETON, M_STAR, M_VALUE, Node,
    P_PARAMSPEC, P_TYPEVAR, S_ANNASSIGN, S_ASSERT, S_ASSIGN, S_AUGASSIGN, S_BREAK, S_CLASSDEF,
    S_CONTINUE, S_DELETE, S_EXPR, S_FOR, S_FUNCTIONDEF, S_GLOBAL, S_IF, S_IMPORT, S_IMPORTFROM,
    S_MATCH, S_NONLOCAL, S_PASS, S_RAISE, S_RETURN, S_TRY, S_TYPEALIAS, S_WHILE, S_WITH,
    X_FS_INTERP, X_FS_LITERAL, X_FSTRING_PART, X_STRING_PART, child,
)
from ._lexer import MODE_EXPRESSION
from ._parser import Parser
from ._tokens import (
    T_COLON, T_COMMA, T_COMMENT, T_DOUBLESTAR, T_LBRACE, T_LPAR, T_LSQB, T_NEWLINE, T_RARROW,
    T_RBRACE, T_RPAR, T_RSQB, T_STAR,
)

TAG_LITERAL_FALSE = 0
TAG_LITERAL_TRUE = 1
TAG_LITERAL_NONE = 2
TAG_LITERAL_INT = 3
TAG_LITERAL_STR = 4
TAG_LITERAL_FLOAT = 6
TAG_LIST_GEN = 20
TAG_LIST_INT = 21
TAG_DICT_STR_GEN = 30
TAG_DECORATOR = 53
TAG_CLASS_DEF = 60
TAG_END = 255
TAG_LOCATION = 152
TAG_EXPR_STMT = 160
TAG_CALL_EXPR = 161
TAG_NAME_EXPR = 162
TAG_STR_EXPR = 163
TAG_IMPORT = 164
TAG_MEMBER_EXPR = 165
TAG_OP_EXPR = 166
TAG_INT_EXPR = 167
TAG_IF = 168
TAG_ASSIGN = 169
TAG_TUPLE_EXPR = 170
TAG_BLOCK = 171
TAG_INDEX = 172
TAG_LIST_EXPR = 173
TAG_SET_EXPR = 174
TAG_RETURN = 175
TAG_WHILE = 176
TAG_COMPARISON_EXPR = 177
TAG_BOOL_OP_EXPR = 178
TAG_FUNC_DEF = 179
TAG_PASS_STMT = 180
TAG_FLOAT_EXPR = 181
TAG_UNARY_EXPR = 182
TAG_DICT_EXPR = 183
TAG_COMPLEX_EXPR = 184
TAG_SLICE_EXPR = 185
TAG_TEMP_NODE = 186
TAG_RAISE_STMT = 187
TAG_BREAK_STMT = 188
TAG_CONTINUE_STMT = 189
TAG_GENERATOR_EXPR = 190
TAG_YIELD_EXPR = 191
TAG_YIELD_FROM_EXPR = 192
TAG_LIST_COMPREHENSION = 193
TAG_SET_COMPREHENSION = 194
TAG_DICT_COMPREHENSION = 195
TAG_IMPORT_FROM = 196
TAG_ASSERT_STMT = 197
TAG_FOR_STMT = 198
TAG_WITH_STMT = 199
TAG_OPERATOR_ASSIGNMENT_STMT = 200
TAG_TRY_STMT = 201
TAG_ELLIPSIS_EXPR = 202
TAG_CONDITIONAL_EXPR = 203
TAG_DEL_STMT = 204
TAG_FSTRING_EXPR = 205
TAG_FSTRING_INTERPOLATION = 206
TAG_LAMBDA_EXPR = 207
TAG_ASSIGNMENT_EXPR = 208
TAG_STAR_EXPR = 209
TAG_BYTES_EXPR = 210
TAG_GLOBAL_DECL = 211
TAG_NONLOCAL_DECL = 212
TAG_AWAIT_EXPR = 213
TAG_BIG_INT_EXPR = 214
TAG_IMPORT_ALL = 215
TAG_MATCH_STMT = 216
TAG_AS_PATTERN = 217
TAG_OR_PATTERN = 218
TAG_VALUE_PATTERN = 219
TAG_SINGLETON_PATTERN = 220
TAG_SEQUENCE_PATTERN = 221
TAG_STARRED_PATTERN = 222
TAG_MAPPING_PATTERN = 223
TAG_CLASS_PATTERN = 224
TAG_TYPE_ALIAS_STMT = 225
TAG_IMPORT_METADATA = 226
TAG_IMPORTFROM_METADATA = 227
TAG_IMPORTALL_METADATA = 228
TAG_TSTRING_EXPR = 229
TAG_UNBOUND_TYPE = 104
TAG_TUPLE_TYPE = 112
TAG_TYPED_DICT_TYPE = 113
TAG_UNION_TYPE = 115
TAG_LIST_TYPE = 118
TAG_ELLIPSIS_TYPE = 119
TAG_RAW_EXPRESSION_TYPE = 120
TAG_CALL_TYPE = 121
TAG_UNPACK_TYPE = 105

ARG_POS = 0
ARG_OPT = 1
ARG_STAR = 2
ARG_NAMED = 3
ARG_STAR2 = 4
ARG_NAMED_OPT = 5

CV_HANDLER_LOCATIONS = 1
CV_RAW_EXPRESSION_TYPE_NOTES = 2
CV_IMPORT_FLAGS = 3
CV_DICT_KEY_OPT = 4
CV_UNICODE_SURROGATE = 5
CV_FUNC_TYPE_COMMENT_FLAG = 6
CV_FULL_TYPE_COMMENTS = 7

IMPORT_FLAG_TOP_LEVEL = 1
IMPORT_FLAG_UNREACHABLE = 2
IMPORT_FLAG_MYPY_ONLY = 4
IMPORT_FLAG_LAZY = 8

# reachability truth values
ALWAYS_TRUE = 1
MYPY_TRUE = 2
ALWAYS_FALSE = 3
MYPY_FALSE = 4
TRUTH_UNKNOWN = 5

# type comments
TC_REGULAR = 0
TC_FUNCTION = 1
TC_INVALID = 2

BYTE: list[bytes] = [bytes([b]) for b in range(256)]
OPERATOR_TEXT: list[bytes] = [b"+", b"-", b"*", b"@", b"/", b"%", b"**", b"<<", b">>", b"|", b"^", b"&", b"//"]


class Options:
    def __init__(self, python_version: tuple[int, int], platform: str, always_true: list[str],
                 always_false: list[str], cache_version: int) -> None:
        self.python_version: tuple[int, int] = python_version
        self.platform: bytes = platform.encode()
        self.always_true: list[bytes] = [s.encode() for s in always_true]
        self.always_false: list[bytes] = [s.encode() for s in always_false]
        self.cache_version: int = cache_version


class TypeComment:
    def __init__(self, kind: int, expr: Node | None, args: list[Node], msg: str) -> None:
        self.kind: int = kind
        self.expr: Node | None = expr  # (the type, or the return type of a function comment)
        self.args: list[Node] = args
        self.msg: str = msg


class SyntaxError_:
    def __init__(self, line: int, column: int, message: str, blocker: bool) -> None:
        self.line: int = line
        self.column: int = column
        self.message: str = message
        self.blocker: bool = blocker


class ImportInfo:
    # kind 0 import, 1 from-import, 2 import-all
    def __init__(self, kind: int, name: bytes, relative: int, as_name: bytes, has_as: bool,
                 names: list[bytes], as_names: list[bytes], has_as_names: list[bool],
                 start: int, end: int, flags: int) -> None:
        self.kind: int = kind
        self.name: bytes = name
        self.relative: int = relative
        self.as_name: bytes = as_name
        self.has_as: bool = has_as
        self.names: list[bytes] = names
        self.as_names: list[bytes] = as_names
        self.has_as_names: list[bool] = has_as_names
        self.start: int = start
        self.end: int = end
        self.flags: int = flags


class LineIndex:
    """ruff_source_file's LineIndex over the (newline-normalized) text, with the serializer's
    per-line ASCII flags."""

    def __init__(self, text: bytes) -> None:
        self.text: bytes = text
        starts: list[int] = [0]
        p = text.find(b"\n")
        while p >= 0:
            starts.append(p + 1)
            p = text.find(b"\n", p + 1)
        self.starts: list[int] = starts
        self.ascii: bool = is_ascii(text)
        self.bom: bool = len(text) >= 3 and text[0] == 0xEF and text[1] == 0xBB and text[2] == 0xBF
        # str::lines(): a line per newline, but no empty last line after a final newline
        self.non_ascii_lines: list[bool] = []
        if not self.ascii:
            nlines = len(starts)
            if starts[-1] == len(text):
                nlines -= 1
            for i in range(nlines):
                s = starts[i]
                e = starts[i + 1] - 1 if i + 1 < len(starts) else len(text)
                self.non_ascii_lines.append(not is_ascii(text[s:e]))

    def line_of(self, offset: int) -> int:
        # 1-based line of offset (binary search of the line starts)
        starts = self.starts
        lo = 0
        hi = len(starts)
        while lo < hi:
            mid = (lo + hi) // 2
            if starts[mid] <= offset:
                lo = mid + 1
            else:
                hi = mid
        return lo

    def line_start(self, line: int) -> int:
        if line - 1 == len(self.starts):
            return len(self.text)
        return self.starts[line - 1]

    def column(self, line: int, offset: int) -> int:
        # LineIndex::line_column's 1-based UTF-32 column of offset on its line
        start = self.starts[line - 1]
        if self.ascii:
            return offset - start + 1
        col = count_chars(self.text, start, offset) + 1
        if line == 1 and self.bom and col > 1:
            col -= 1
        return col

    def convert(self, line: int, col: int) -> int:
        # convert_column_to_codepoint: col (really a character column) taken as a byte offset
        idx = line - 1
        if idx < 0:
            idx = 0
        if idx < len(self.non_ascii_lines) and self.non_ascii_lines[idx]:
            start = self.line_start(idx + 1)
            target = start + col
            text = self.text
            if target > len(text):
                target = len(text)
            while target > 0 and target < len(text) and (text[target] & 0xC0) == 0x80:
                target -= 1
            return count_chars(text, start, target)
        return col


def is_ascii(b: bytes) -> bool:
    for c in b:
        if c >= 0x80:
            return False
    return True


def count_chars(text: bytes, start: int, end: int) -> int:
    n = 0
    for i in range(start, end):
        if (text[i] & 0xC0) != 0x80:
            n += 1
    return n


class Serializer:
    def __init__(self, text: bytes, li: LineIndex, options: Options, skip_function_bodies: bool,
                 tokens: Parser | None, type_comments: dict[int, TypeComment]) -> None:
        self.out: list[bytes] = []
        self.imports: list[ImportInfo] = []
        self.text: bytes = text
        self.li: LineIndex = li
        self.options: Options = options
        self.cv: int = options.cache_version
        self.skip_function_bodies: bool = skip_function_bodies
        self.tokens: Parser | None = tokens
        self.type_comments: dict[int, TypeComment] = type_comments
        self.in_class = False
        self.in_function = False
        self.current_unreachable = False
        self.current_mypy_only = False
        self.top_level_getattr = False
        self.is_evaluated = True
        self.extra_errors: list[SyntaxError_] = []
        self.skipped_lines: dict[int, bool] = {}
        self.uses_template_strings = False
        self.has_surrogates = False
        self.saved_u: list[bool] = []
        self.saved_m: list[bool] = []
        self.override = False
        self.o_line = 0
        self.o_col = 0
        self.o_end_line = 0
        self.o_end_col = 0

    # -- primitives
    def tag(self, t: int) -> None:
        self.out.append(BYTE[t])

    def end(self) -> None:
        self.out.append(BYTE[TAG_END])

    def int_(self, i: int) -> None:
        out = self.out
        if -10 <= i < 118:
            out.append(BYTE[(i + 10) << 1])
        elif -100 <= i <= 16283:
            x = ((i + 100) << 2) | 1
            out.append(bytes([x & 255, x >> 8]))
        elif -10000 <= i <= 536860911:
            x = ((i + 10000) << 3) | 3
            out.append(bytes([x & 255, (x >> 8) & 255, (x >> 16) & 255, x >> 24]))
        else:
            out.append(BYTE[15])
            neg = i < 0
            v = -i if neg else i
            bs: list[int] = []
            while v > 0:
                bs.append(v & 255)
                v >>= 8
            if len(bs) == 0:
                bs.append(0)
            self.int_((len(bs) << 1) | (1 if neg else 0))
            out.append(bytes(bs))

    def tagged_int(self, i: int) -> None:
        self.out.append(BYTE[TAG_LITERAL_INT])
        self.int_(i)

    def str_(self, b: bytes) -> None:
        self.out.append(BYTE[TAG_LITERAL_STR])
        self.int_(len(b))
        self.out.append(b)

    def bool_(self, b: bool) -> None:
        self.out.append(BYTE[1] if b else BYTE[0])

    def none(self) -> None:
        self.out.append(BYTE[TAG_LITERAL_NONE])

    def float_(self, f: float) -> None:
        self.out.append(BYTE[TAG_LITERAL_FLOAT])
        self.out.append(struct.pack("<d", f))

    def getvalue(self) -> bytes:
        return b"".join(self.out)

    # -- locations
    def location(self, start: int, end: int) -> None:
        self.out.append(BYTE[TAG_LOCATION])
        if self.override:
            self.int_(self.o_line)
            self.int_(self.o_col)
            self.int_(self.o_end_line - self.o_line)
            self.int_(self.o_end_col - self.o_col)
            return
        li = self.li
        st_line = li.line_of(start)
        st_col = li.column(st_line, start)
        end_line = li.line_of(end)
        end_col = li.column(end_line, end)
        if li.ascii:
            self.int_(st_line)
            self.int_(st_col - 1)
            self.int_(end_line - st_line)
            self.int_(end_col - st_col)
        else:
            c1 = li.convert(st_line, st_col)
            c2 = li.convert(end_line, end_col)
            self.int_(st_line)
            self.int_(c1 - 1)
            self.int_(end_line - st_line)
            self.int_(c2 - c1)

    def line_column(self, offset: int) -> tuple[int, int]:
        line = self.li.line_of(offset)
        return line, self.li.column(line, offset)

    def skip_lines(self, first: Node, last: Node) -> None:
        st = self.li.line_of(first.start)
        en = self.li.line_of(last.end)
        for line in range(st, en + 1):
            self.skipped_lines[line] = True

    def add_error(self, msg: str, start: int, blocker: bool) -> None:
        line, col = self.line_column(start)
        c = self.li.convert(line, col)
        self.extra_errors.append(SyntaxError_(line, c - 1, msg, blocker))

    def check_surrogate_codepoint(self, part: Node) -> None:
        # (the part's value holds U+FFFD: look for a surrogate escape in its source text)
        if part.s.find(b"\xef\xbf\xbd") < 0:
            return
        if self.has_surrogates:
            return
        text = self.text
        i = part.start
        end = part.end
        while i < end:
            c = text[i]
            if c == 92 and i + 1 < end:
                nc = text[i + 1]
                if nc == 117 or nc == 85:
                    size = 4 if nc == 117 else 8
                    digits = text[i + 2:i + 2 + size]
                    try:
                        v = int(digits.decode(), 16)
                    except ValueError:
                        v = 0
                    if 0xD800 <= v <= 0xDFFF:
                        self.has_surrogates = True
                        return
                    i += 2 + size
                    continue
                i += 2
                if nc >= 0x80:
                    i += char_tail(nc)
                continue
            i += 1

    # -- blocks
    def block(self, stmts: list[Node], fallback: Node | None) -> None:
        self.tag(TAG_BLOCK)
        self.tag(TAG_LIST_GEN)
        self.int_(len(stmts))
        self.bool_(self.current_unreachable)
        if len(stmts) > 0 and self.current_unreachable:
            self.skip_lines(stmts[0], stmts[-1])
        if len(stmts) == 0 and fallback is not None:
            self.location(fallback.start, fallback.end)
        for s in stmts:
            self.stmt(s)
        self.end()

    def empty_block(self, start: int, end: int) -> None:
        self.tag(TAG_BLOCK)
        self.tag(TAG_LIST_GEN)
        self.int_(0)
        self.bool_(self.current_unreachable)
        self.location(start, end)
        self.end()

    def exprs(self, xs: list[Node]) -> None:
        self.tag(TAG_LIST_GEN)
        self.int_(len(xs))
        for x in xs:
            self.expr(x)

    def opt_expr(self, x: Node | None) -> None:
        if x is not None:
            self.bool_(True)
            self.expr(x)
        else:
            self.bool_(False)

    # -- module
    def module(self, body: list[Node]) -> None:
        stmts: list[Node] = []
        for i in range(len(body)):
            s = body[i]
            stmts.append(s)
            if assert_will_always_fail(s, self.options):
                if i < len(body) - 1:
                    self.skip_lines(body[i + 1], body[-1])
                break
        self.tagged_int(len(stmts))
        for s in stmts:
            self.stmt(s)

    # -- statements
    def stmt(self, s: Node) -> None:
        k = s.kind
        if k == S_FUNCTIONDEF:
            self.function_def(s)
        elif k == S_EXPR:
            self.tag(TAG_EXPR_STMT)
            self.expr(child(s.a))
        elif k == S_ASSIGN:
            self.assign(s)
        elif k == S_ANNASSIGN:
            self.tag(TAG_ASSIGN)
            self.tag(TAG_LIST_GEN)
            self.int_(1)
            self.expr(child(s.a))
            if s.c is not None:
                self.expr(s.c)
            else:
                self.tag(TAG_TEMP_NODE)
                self.end()
            self.bool_(True)
            self.type_(child(s.b))
            self.bool_(True)
            self.location(s.start, s.end)
        elif k == S_AUGASSIGN:
            self.tag(TAG_OPERATOR_ASSIGNMENT_STMT)
            self.str_(OPERATOR_TEXT[s.n])
            self.expr(child(s.a))
            self.expr(child(s.b))
            self.location(s.start, s.end)
        elif k == S_IMPORT:
            flags = self.import_flags(s.flag)
            self.tag(TAG_IMPORT)
            self.tagged_int(len(s.xs))
            for alias in s.xs:
                self.str_(alias.s)
                if alias.flag:
                    self.bool_(True)
                    self.str_(alias.s2)
                else:
                    self.bool_(False)
                self.imports.append(ImportInfo(0, alias.s, 0, alias.s2, alias.flag, [], [], [],
                                               alias.start, alias.end, flags))
            self.location(s.start, s.end)
            if self.cv >= CV_IMPORT_FLAGS:
                self.tagged_int(flags)
        elif k == S_IMPORTFROM:
            self.import_from(s)
        elif k == S_RETURN:
            self.tag(TAG_RETURN)
            self.opt_expr(s.a)
            self.location(s.start, s.end)
        elif k == S_RAISE:
            self.tag(TAG_RAISE_STMT)
            self.opt_expr(s.a)
            self.opt_expr(s.b)
            self.location(s.start, s.end)
        elif k == S_ASSERT:
            self.tag(TAG_ASSERT_STMT)
            self.expr(child(s.a))
            self.opt_expr(s.b)
            self.location(s.start, s.end)
        elif k == S_IF:
            self.if_stmt(s)
        elif k == S_WHILE:
            self.tag(TAG_WHILE)
            self.expr(child(s.a))
            self.block(s.ys, s)
            self.block(s.zs, None)
            self.location(s.start, s.end)
        elif k == S_FOR:
            self.tag(TAG_FOR_STMT)
            self.expr(child(s.a))
            self.expr(child(s.b))
            self.block(s.ys, s)
            self.block(s.zs, None)
            self.bool_(s.flag)
            self.location(s.start, s.end)
        elif k == S_WITH:
            self.tag(TAG_WITH_STMT)
            self.tagged_int(len(s.xs))
            for item in s.xs:
                self.expr(child(item.a))
                self.opt_expr(item.b)
            self.block(s.ys, s)
            self.bool_(s.flag)
            self.location(s.start, s.end)
        elif k == S_PASS:
            self.tag(TAG_PASS_STMT)
            self.location(s.start, s.end)
        elif k == S_BREAK:
            self.tag(TAG_BREAK_STMT)
            self.location(s.start, s.end)
        elif k == S_CONTINUE:
            self.tag(TAG_CONTINUE_STMT)
            self.location(s.start, s.end)
        elif k == S_CLASSDEF:
            self.class_def(s)
        elif k == S_TRY:
            self.try_stmt(s)
        elif k == S_DELETE:
            self.tag(TAG_DEL_STMT)
            if len(s.xs) == 1:
                self.expr(s.xs[0])
            else:
                self.tag(TAG_TUPLE_EXPR)
                self.exprs(s.xs)
                self.location(s.start, s.end)
                self.end()
            self.location(s.start, s.end)
        elif k == S_GLOBAL or k == S_NONLOCAL:
            self.tag(TAG_GLOBAL_DECL if k == S_GLOBAL else TAG_NONLOCAL_DECL)
            self.tagged_int(len(s.xs))
            for name in s.xs:
                self.str_(name.s)
            self.location(s.start, s.end)
        elif k == S_MATCH:
            self.match_stmt(s)
        elif k == S_TYPEALIAS:
            self.tag(TAG_TYPE_ALIAS_STMT)
            self.expr(child(s.a))
            tp = s.c
            if tp is not None:
                self.int_(len(tp.xs))
                self.type_params(tp)
            else:
                self.int_(0)
            self.expr(child(s.b))
            self.location(s.start, s.end)
        else:
            raise ValueError("unsupported statement")
        self.end()

    def import_flags(self, lazy: bool) -> int:
        f = 0
        if not self.in_function:
            f |= IMPORT_FLAG_TOP_LEVEL
        if self.current_unreachable:
            f |= IMPORT_FLAG_UNREACHABLE
        if self.current_mypy_only:
            f |= IMPORT_FLAG_MYPY_ONLY
        if lazy:
            f |= IMPORT_FLAG_LAZY
        return f

    def import_from(self, s: Node) -> None:
        flags = self.import_flags(s.flag)
        module = s.s if s.flag2 else b""
        if len(s.xs) == 1 and s.xs[0].s == b"*":
            self.tag(TAG_IMPORT_ALL)
            self.str_(module)
            self.tagged_int(s.n)
            self.location(s.start, s.end)
            if self.cv >= CV_IMPORT_FLAGS:
                self.tagged_int(flags)
            self.imports.append(ImportInfo(2, module, s.n, b"", False, [], [], [], s.start, s.end, flags))
            return
        self.tag(TAG_IMPORT_FROM)
        self.tagged_int(s.n)
        self.str_(module)
        self.tagged_int(len(s.xs))
        names: list[bytes] = []
        as_names: list[bytes] = []
        has_as: list[bool] = []
        for alias in s.xs:
            self.str_(alias.s)
            if alias.flag:
                self.bool_(True)
                self.str_(alias.s2)
            else:
                self.bool_(False)
            names.append(alias.s)
            as_names.append(alias.s2)
            has_as.append(alias.flag)
        self.imports.append(ImportInfo(1, module, s.n, b"", False, names, as_names, has_as, s.start, s.end, flags))
        self.location(s.start, s.end)
        if self.cv >= CV_IMPORT_FLAGS:
            self.tagged_int(flags)

    def assign(self, s: Node) -> None:
        self.tag(TAG_ASSIGN)
        self.exprs(s.xs)
        self.expr(child(s.a))
        line = self.li.line_of(s.start)
        end_line = self.li.line_of(s.end)
        tc = self.type_comments.get(line)
        if tc is None:
            tc = self.type_comments.get(end_line)
        if tc is not None and tc.kind == TC_REGULAR:
            self.bool_(True)
            t = child(tc.expr)
            relocate(t, s.start, s.end)
            was = self.is_evaluated
            self.is_evaluated = False
            self.type_(t)
            self.is_evaluated = was
        elif tc is not None and tc.kind == TC_INVALID:
            self.add_error(tc.msg, s.start, False)
            self.bool_(True)
            self.invalid_type(b"", False)
            self.location(s.start, s.end)
            self.end()
        else:
            self.bool_(False)
        self.bool_(False)
        self.location(s.start, s.end)

    def function_def(self, f: Node) -> None:
        params = child(f.a)
        arg_comments, ret_comment = self.find_func_type_comment(f)
        decorated = len(f.xs) > 0
        if decorated:
            self.tag(TAG_DECORATOR)
            self.tag(TAG_LIST_GEN)
            self.int_(len(f.xs))
            for d in f.xs:
                self.expr(child(d.a))
            line, col = self.line_column(f.xs[0].start)
            self.tagged_int(line)
            self.tagged_int(col)
        self.tag(TAG_FUNC_DEF)
        self.str_(f.s)
        self.parameters(params, arg_comments)
        if self.skip_function_bodies:
            serialize_body = has_externally_visible_effect(f.ys, params, self.in_class)
        else:
            serialize_body = True
        if not self.in_class and not self.in_function and f.s == b"__getattr__":
            self.top_level_getattr = True
        was_in_function = self.in_function
        self.in_function = True
        if serialize_body:
            self.block(f.ys, f)
        elif len(f.ys) > 0:
            self.empty_block(f.ys[0].start, f.ys[-1].end)
        else:
            self.empty_block(f.start, f.end)
        self.in_function = was_in_function
        self.bool_(f.flag)
        tp = f.c
        if tp is not None:
            self.bool_(True)
            self.int_(len(tp.xs))
            self.type_params(tp)
        else:
            self.bool_(False)
        if f.b is not None and ret_comment is not None:
            self.add_error("Function has duplicate type signatures", f.start, False)
        if f.b is not None:
            self.bool_(True)
            self.type_(f.b)
        elif ret_comment is not None:
            self.bool_(True)
            relocate(ret_comment, f.start, f.end)
            was = self.is_evaluated
            self.is_evaluated = False
            self.type_(ret_comment)
            self.is_evaluated = was
        else:
            self.bool_(False)
        if self.cv >= CV_FUNC_TYPE_COMMENT_FLAG:
            any_comment = ret_comment is not None
            for ac in arg_comments:
                if ac is not None:
                    any_comment = True
            self.bool_(any_comment)
        if decorated:
            self.tag(TAG_LOCATION)
            name_line, name_col = self.line_column(f.nstart)
            end_line, end_col = self.line_column(f.end)
            def_column = (name_col - 1) - (10 if f.flag else 4)
            self.int_(name_line)
            self.int_(def_column)
            self.int_(end_line - name_line)
            self.int_((end_col - 1) - def_column)
            self.end()
        else:
            self.location(f.start, f.end)

    def find_func_type_comment(self, f: Node) -> tuple[list[Node | None], Node | None]:
        params = child(f.a)
        nparams = param_count(params)
        arg_types: list[Node | None] = [None] * nparams
        ret_type: Node | None = None
        if len(f.ys) == 0:
            return arg_types, ret_type
        toks = self.tokens
        if toks is None:
            return arg_types, ret_type
        first_stmt = f.ys[0].start
        # Tokens::before: the tokens that start before the first statement
        idx = token_partition(toks.tok_start, first_stmt) - 1
        while True:
            k = toks.tok_kind[idx]
            if idx == 0 or k == T_COLON:
                break
            if k == T_COMMENT:
                line = self.li.line_of(toks.tok_start[idx])
                tc = self.type_comments.get(line)
                if tc is not None and tc.kind == TC_FUNCTION:
                    ret_type = tc.expr
                    args = tc.args
                    if len(args) == 1 and args[0].kind == E_ELLIPSIS:
                        break
                    if len(args) == nparams:
                        for i in range(len(args)):
                            arg_types[i] = args[i]
                    elif self.in_class and len(args) == nparams - 1:
                        for i in range(1, nparams):
                            arg_types[i] = args[i - 1]
                    else:
                        msg = "Type signature has too many parameters" if len(args) > nparams else "Type signature has too few parameters"
                        self.add_error(msg, f.start, False)
                    break
                if tc is not None and tc.kind == TC_INVALID:
                    self.add_error(tc.msg, f.start, False)
                    break
            idx -= 1
        i = 0
        for p in all_params(params):
            line = self.li.line_of(p.start)
            tc = self.type_comments.get(line)
            if tc is not None and tc.kind == TC_REGULAR:
                if arg_types[i] is not None:
                    self.add_error("Function has duplicate type signatures", f.start, False)
                else:
                    arg_types[i] = tc.expr
            i += 1
        return arg_types, ret_type

    def parameters(self, params: Node, arg_comments: list[Node | None]) -> None:
        count = param_count(params)
        self.tag(TAG_LIST_GEN)
        self.int_(count)
        idx = 0
        for pd in params.xs:
            self.argument(child(pd.a), arg_comments[idx], pd.b, ARG_POS, ARG_OPT, True)
            idx += 1
        for pd in params.ys:
            p = child(pd.a)
            name = p.s
            pos_only = name.startswith(b"__") and not name.endswith(b"__")
            self.argument(p, arg_comments[idx], pd.b, ARG_POS, ARG_OPT, pos_only)
            idx += 1
        if params.a is not None:
            self.argument(params.a, arg_comments[idx], None, ARG_STAR, ARG_STAR, False)
            idx += 1
        for pd in params.zs:
            self.argument(child(pd.a), arg_comments[idx], pd.b, ARG_NAMED, ARG_NAMED_OPT, False)
            idx += 1
        if params.b is not None:
            self.argument(params.b, arg_comments[idx], None, ARG_STAR2, ARG_STAR2, False)

    def argument(self, p: Node, comment: Node | None, default: Node | None, kind_plain: int,
                 kind_default: int, pos_only: bool) -> None:
        self.str_(p.s)
        self.tagged_int(kind_default if default is not None else kind_plain)
        if p.a is not None and comment is not None:
            self.add_error("Function has duplicate type signatures", p.start, False)
        if p.a is not None:
            self.bool_(True)
            self.type_(p.a)
        elif comment is not None:
            self.bool_(True)
            relocate(comment, p.start, p.end)
            was = self.is_evaluated
            self.is_evaluated = False
            self.type_(comment)
            self.is_evaluated = was
        else:
            self.bool_(False)
        self.opt_expr(default)
        self.bool_(pos_only)
        self.location(p.start, p.end)

    def type_params(self, tp: Node) -> None:
        for t in tp.xs:
            if t.kind == P_TYPEVAR:
                self.tagged_int(0)
                self.str_(t.s)
                bound = t.a
                values: list[Node] = []
                has_bound = False
                if bound is not None:
                    if bound.kind == E_TUPLE:
                        values = bound.xs
                    else:
                        has_bound = True
                if has_bound:
                    self.bool_(True)
                    self.type_(child(bound))
                else:
                    self.bool_(False)
                self.tag(TAG_LIST_GEN)
                self.int_(len(values))
                for v in values:
                    self.type_(v)
            else:
                self.tagged_int(1 if t.kind == P_PARAMSPEC else 2)
                self.str_(t.s)
                self.bool_(False)
                self.tag(TAG_LIST_GEN)
                self.int_(0)
            if t.b is not None:
                self.bool_(True)
                self.type_(t.b)
            else:
                self.bool_(False)

    def class_def(self, c: Node) -> None:
        self.tag(TAG_CLASS_DEF)
        self.str_(c.s)
        was_in_class = self.in_class
        self.in_class = True
        self.block(c.ys, c)
        self.in_class = was_in_class
        args = c.a
        self.tag(TAG_LIST_GEN)
        if args is not None:
            self.int_(len(args.xs))
            for base in args.xs:
                self.expr(base)
        else:
            self.int_(0)
        self.tag(TAG_LIST_GEN)
        self.int_(len(c.xs))
        for d in c.xs:
            self.expr(child(d.a))
        tp = c.c
        if tp is not None:
            self.bool_(True)
            self.int_(len(tp.xs))
            self.type_params(tp)
        else:
            self.bool_(False)
        self.tag(TAG_DICT_STR_GEN)
        if args is not None:
            named = [kw for kw in args.ys if kw.flag]
            self.int_(len(named))
            for kw in named:
                self.str_(kw.s)
                self.expr(child(kw.a))
        else:
            self.int_(0)
        if len(c.xs) > 0:
            self.tag(TAG_LOCATION)
            _, dec_col = self.line_column(c.xs[-1].start)
            name_line, _ = self.line_column(c.nstart)
            end_line, end_col = self.line_column(c.end)
            st_col = dec_col - 1
            self.int_(name_line)
            self.int_(st_col)
            self.int_(end_line - name_line)
            self.int_((end_col - 1) - st_col)
        else:
            self.location(c.start, c.end)

    def try_stmt(self, t: Node) -> None:
        self.tag(TAG_TRY_STMT)
        self.block(t.ys, t)
        self.tagged_int(len(t.xs))
        for h in t.xs:
            typ = h.a
            if typ is not None:
                self.bool_(True)
                self.expr(typ)
                if typ.kind == E_TUPLE:
                    if self.options.python_version < (3, 14) and not typ.flag and not h.flag:
                        self.add_error("multiple exception types must be parenthesized", typ.start, False)
            else:
                self.bool_(False)
        for h in t.xs:
            if h.flag:
                self.bool_(True)
                self.str_(h.s)
                if self.cv >= CV_HANDLER_LOCATIONS:
                    self.location(h.nstart, h.nend)
            else:
                self.bool_(False)
        for h in t.xs:
            self.block(h.ys, h)
        if len(t.zs) > 0:
            self.bool_(True)
            self.block(t.zs, t)
        else:
            self.bool_(False)
        if len(t.ws) > 0:
            self.bool_(True)
            self.block(t.ws, t)
        else:
            self.bool_(False)
        self.bool_(t.flag)
        self.location(t.start, t.end)

    def match_stmt(self, m: Node) -> None:
        an = IfAnalyzer(self.options)
        flags: list[tuple[bool, bool]] = []
        for case in m.xs:
            flags.append(an.match_case_flags(child(case.a), case.b))
        self.tag(TAG_MATCH_STMT)
        self.expr(child(m.a))
        self.tagged_int(len(m.xs))
        for i in range(len(m.xs)):
            case = m.xs[i]
            self.pattern(child(case.a))
            self.opt_expr(case.b)
            unreachable, mypy_only = flags[i]
            old_u = self.current_unreachable
            old_m = self.current_mypy_only
            self.current_unreachable = old_u or unreachable
            self.current_mypy_only = old_m or mypy_only
            self.block(case.ys, case)
            self.current_unreachable = old_u
            self.current_mypy_only = old_m
        self.location(m.start, m.end)

    def if_stmt(self, s: Node) -> None:
        clauses = s.xs
        has_else = len(clauses) > 0 and clauses[-1].a is None
        an = IfAnalyzer(self.options)
        main_flags = an.condition_flags(child(s.a))
        clause_flags: list[tuple[bool, bool]] = []
        for cl in clauses:
            if cl.a is not None:
                clause_flags.append(an.condition_flags(cl.a))
            else:
                clause_flags.append(an.else_flags())
        synthetic = an.else_flags()
        self.tag(TAG_IF)
        self.expr(child(s.a))
        self.with_flags(main_flags)
        self.block(s.ys, s)
        self.restore_flags()
        self.tagged_int(len(clauses) - (1 if has_else else 0))
        for i in range(len(clauses)):
            cl = clauses[i]
            if cl.a is not None:
                self.expr(cl.a)
            else:
                self.bool_(True)
            self.with_flags(clause_flags[i])
            self.block(cl.ys, cl)
            self.restore_flags()
        if not has_else:
            if synthetic[0]:
                self.bool_(True)
                self.with_flags(synthetic)
                self.empty_block(s.start, s.end)
                self.restore_flags()
            else:
                self.bool_(False)
        self.location(s.start, s.end)

    def with_flags(self, flags: tuple[bool, bool]) -> None:
        self.saved_u.append(self.current_unreachable)
        self.saved_m.append(self.current_mypy_only)
        self.current_unreachable = self.current_unreachable or flags[0]
        self.current_mypy_only = self.current_mypy_only or flags[1]

    def restore_flags(self) -> None:
        self.current_unreachable = self.saved_u.pop()
        self.current_mypy_only = self.saved_m.pop()

    # -- expressions
    def expr(self, e: Node) -> None:
        k = e.kind
        if k == E_NAME:
            self.tag(TAG_NAME_EXPR)
            self.str_(e.s)
            self.location(e.start, e.end)
        elif k == E_ATTRIBUTE:
            self.tag(TAG_MEMBER_EXPR)
            self.expr(child(e.a))
            self.str_(e.s)
            self.location(e.start, e.end)
        elif k == E_STRING:
            self.tag(TAG_STR_EXPR)
            total = 0
            for part in e.xs:
                total += len(part.s)
            self.out.append(BYTE[TAG_LITERAL_STR])
            self.int_(total)
            self.has_surrogates = False
            for part in e.xs:
                self.out.append(part.s)
                self.check_surrogate_codepoint(part)
            if self.cv >= CV_UNICODE_SURROGATE:
                self.bool_(self.has_surrogates)
            self.location(e.start, e.end)
        elif k == E_CALL:
            self.call(e)
        elif k == E_BINOP:
            self.tag(TAG_OP_EXPR)
            self.tagged_int(e.n)
            self.expr(child(e.a))
            self.expr(child(e.b))
        elif k == E_INT:
            if e.flag:
                self.tag(TAG_INT_EXPR)
                self.tagged_int(e.ival)
            else:
                self.tag(TAG_BIG_INT_EXPR)
                self.str_(e.s)
            self.location(e.start, e.end)
        elif k == E_FLOAT:
            self.tag(TAG_FLOAT_EXPR)
            self.float_(e.fval)
            self.location(e.start, e.end)
        elif k == E_COMPLEX:
            self.tag(TAG_COMPLEX_EXPR)
            self.float_(0.0)
            self.float_(e.fval)
            self.location(e.start, e.end)
        elif k == E_SUBSCRIPT:
            self.tag(TAG_INDEX)
            self.expr(child(e.a))
            self.expr(child(e.b))
            self.location(e.start, e.end)
        elif k == E_LIST:
            self.tag(TAG_TUPLE_EXPR if e.n == CTX_STORE else TAG_LIST_EXPR)
            self.exprs(e.xs)
            self.location(e.start, e.end)
        elif k == E_TUPLE:
            self.tag(TAG_TUPLE_EXPR)
            self.exprs(e.xs)
            self.location(e.start, e.end)
        elif k == E_SET:
            self.tag(TAG_SET_EXPR)
            self.exprs(e.xs)
            self.location(e.start, e.end)
        elif k == E_GENERATOR or k == E_LISTCOMP or k == E_SETCOMP:
            if k == E_GENERATOR:
                self.tag(TAG_GENERATOR_EXPR)
            elif k == E_LISTCOMP:
                self.tag(TAG_LIST_COMPREHENSION)
            else:
                self.tag(TAG_SET_COMPREHENSION)
            self.expr(child(e.a))
            self.comprehensions(e.xs)
            self.location(e.start, e.end)
        elif k == E_DICTCOMP:
            self.tag(TAG_DICT_COMPREHENSION)
            if self.cv >= CV_DICT_KEY_OPT:
                self.opt_expr(e.a)
            elif e.a is not None:
                self.expr(e.a)
            else:
                self.add_error("PEP 798 is not supported yet", e.start, True)
                self.tag(TAG_NAME_EXPR)
                self.str_(b"None")
                self.location(e.start, e.end)
            self.expr(child(e.b))
            self.comprehensions(e.xs)
            self.location(e.start, e.end)
        elif k == E_YIELD:
            self.tag(TAG_YIELD_EXPR)
            self.opt_expr(e.a)
            self.location(e.start, e.end)
        elif k == E_YIELDFROM:
            self.tag(TAG_YIELD_FROM_EXPR)
            self.expr(child(e.a))
            self.location(e.start, e.end)
        elif k == E_BOOLOP:
            self.tag(TAG_BOOL_OP_EXPR)
            self.tagged_int(e.n)
            self.exprs(e.xs)
            self.location(e.start, e.end)
        elif k == E_COMPARE:
            self.tag(TAG_COMPARISON_EXPR)
            self.expr(child(e.a))
            self.tag(TAG_LIST_INT)
            self.int_(len(e.ints))
            for op in e.ints:
                self.int_(op)
            self.exprs(e.ys)
            self.location(e.start, e.end)
        elif k == E_BOOL:
            self.tag(TAG_NAME_EXPR)
            self.str_(b"True" if e.flag else b"False")
            self.location(e.start, e.end)
        elif k == E_NONE:
            self.tag(TAG_NAME_EXPR)
            self.str_(b"None")
            self.location(e.start, e.end)
        elif k == E_ELLIPSIS:
            self.tag(TAG_ELLIPSIS_EXPR)
            self.location(e.start, e.end)
        elif k == E_IF:
            self.tag(TAG_CONDITIONAL_EXPR)
            self.expr(child(e.a))
            self.expr(child(e.b))
            self.expr(child(e.c))
            self.location(e.start, e.end)
        elif k == E_UNARYOP:
            self.tag(TAG_UNARY_EXPR)
            self.tagged_int(e.n)
            self.expr(child(e.a))
            self.location(e.start, e.end)
        elif k == E_DICT:
            self.tag(TAG_DICT_EXPR)
            self.tag(TAG_LIST_GEN)
            self.int_(len(e.xs))
            for item in e.xs:
                if item.a is not None:
                    self.bool_(True)
                    self.expr(item.a)
                else:
                    self.bool_(False)
            self.tag(TAG_LIST_GEN)
            self.int_(len(e.xs))
            for item in e.xs:
                self.expr(child(item.b))
            self.location(e.start, e.end)
        elif k == E_SLICE:
            self.tag(TAG_SLICE_EXPR)
            self.opt_expr(e.a)
            self.opt_expr(e.b)
            self.opt_expr(e.c)
            self.location(e.start, e.end)
        elif k == E_FSTRING:
            self.tag(TAG_FSTRING_EXPR)
            self.tagged_int(len(e.xs))
            self.has_surrogates = False
            for part in e.xs:
                if part.kind == X_FSTRING_PART:
                    self.bool_(True)
                    self.fstring_elements(part.xs)
                else:
                    self.bool_(False)
                    self.str_(part.s)
                    self.check_surrogate_codepoint(part)
                    self.location(part.start, part.end)
            if self.cv >= CV_UNICODE_SURROGATE:
                self.bool_(self.has_surrogates)
            self.location(e.start, e.end)
        elif k == E_LAMBDA:
            self.tag(TAG_LAMBDA_EXPR)
            params = e.a
            if params is not None:
                self.parameters(params, [None] * param_count(params))
            else:
                self.tag(TAG_LIST_GEN)
                self.int_(0)
            body = child(e.b)
            self.tag(TAG_BLOCK)
            self.tag(TAG_LIST_GEN)
            self.int_(1)
            self.bool_(self.current_unreachable)
            self.tag(TAG_RETURN)
            self.bool_(True)
            self.expr(body)
            self.location(body.start, body.end)
            self.end()
            self.end()
            self.location(e.start, e.end)
        elif k == E_NAMED:
            self.tag(TAG_ASSIGNMENT_EXPR)
            self.expr(child(e.a))
            self.expr(child(e.b))
            self.location(e.start, e.end)
        elif k == E_STARRED:
            self.tag(TAG_STAR_EXPR)
            self.expr(child(e.a))
            self.location(e.start, e.end)
        elif k == E_BYTES:
            self.tag(TAG_BYTES_EXPR)
            self.str_(bytes_escaped(e))
            self.location(e.start, e.end)
        elif k == E_AWAIT:
            self.tag(TAG_AWAIT_EXPR)
            self.expr(child(e.a))
            self.location(e.start, e.end)
        elif k == E_TSTRING:
            self.tstring(e)
        else:
            raise ValueError("unsupported expression")
        self.end()

    def call(self, c: Node) -> None:
        self.tag(TAG_CALL_EXPR)
        self.expr(child(c.a))
        args = child(c.b)
        total = len(args.xs) + len(args.ys)
        self.tag(TAG_LIST_GEN)
        self.int_(total)
        for a in args.xs:
            if a.kind == E_STARRED:
                self.expr(child(a.a))
            else:
                self.expr(a)
        for kw in args.ys:
            self.expr(child(kw.a))
        self.tag(TAG_LIST_INT)
        self.int_(total)
        for a in args.xs:
            self.int_(ARG_STAR if a.kind == E_STARRED else ARG_POS)
        for kw in args.ys:
            self.int_(ARG_NAMED if kw.flag else ARG_STAR2)
        self.tag(TAG_LIST_GEN)
        self.int_(total)
        for _ in args.xs:
            self.none()
        for kw in args.ys:
            if kw.flag:
                self.str_(kw.s)
            else:
                self.none()
        self.location(c.start, c.end)

    def comprehensions(self, gens: list[Node]) -> None:
        self.tagged_int(len(gens))
        for g in gens:
            self.expr(child(g.a))
        for g in gens:
            self.expr(child(g.b))
        for g in gens:
            self.exprs(g.xs)
        for g in gens:
            self.bool_(g.flag)

    def tstring(self, e: Node) -> None:
        self.uses_template_strings = True
        self.tag(TAG_TSTRING_EXPR)
        elements: list[Node] = []
        for part in e.xs:
            for el in part.xs:
                elements.append(el)
        self.tagged_int(len(elements))
        self.has_surrogates = False
        for el in elements:
            if el.kind == X_FS_INTERP:
                self.bool_(True)
                value = child(el.a)
                self.expr(value)
                self.str_(self.text[value.start:value.end])
                if el.n == -1:
                    self.bool_(False)
                else:
                    self.bool_(True)
                    self.str_(b"s" if el.n == 115 else (b"r" if el.n == 114 else b"a"))
                spec = el.b
                if spec is not None:
                    self.bool_(True)
                    self.fstring_elements(spec.xs)
                    self.location(spec.start, spec.end)
                else:
                    self.bool_(False)
            else:
                self.bool_(False)
                self.str_(el.s)
                self.check_surrogate_codepoint(el)
                self.location(el.start, el.end)
        if self.cv >= CV_UNICODE_SURROGATE:
            self.bool_(self.has_surrogates)
        self.location(e.start, e.end)

    def fstring_elements(self, elems: list[Node]) -> None:
        extra = 0
        for el in elems:
            if el.kind == X_FS_INTERP and el.flag:
                extra += 1
        self.tagged_int(len(elems) + extra)
        for el in elems:
            if el.kind == X_FS_LITERAL:
                self.str_(el.s)
                self.check_surrogate_codepoint(el)
                self.location(el.start, el.end)
                continue
            value = child(el.a)
            use_r = False
            if el.flag:
                self.str_(el.s + self.text[value.start:value.end] + el.s2)
                self.location(value.start, value.end)
                if el.n == -1 and el.b is None:
                    use_r = True
            self.tag(TAG_FSTRING_INTERPOLATION)
            self.expr(value)
            conv = 114 if use_r else el.n
            if conv == -1:
                self.bool_(False)
            else:
                self.bool_(True)
                self.str_(b"!s" if conv == 115 else (b"!r" if conv == 114 else b"!a"))
            spec = el.b
            if spec is not None:
                self.bool_(True)
                self.fstring_elements(spec.xs)
                self.location(spec.start, spec.end)
            else:
                self.bool_(False)
            self.end()

    # -- patterns
    def pattern(self, p: Node) -> None:
        k = p.kind
        if k == M_AS:
            self.tag(TAG_AS_PATTERN)
            if p.a is not None:
                self.bool_(True)
                self.pattern(p.a)
            else:
                self.bool_(False)
            if p.flag:
                self.bool_(True)
                self.str_(p.s)
                self.location(p.nstart, p.nend)
            else:
                self.bool_(False)
            self.location(p.start, p.end)
        elif k == M_OR:
            self.tag(TAG_OR_PATTERN)
            self.tagged_int(len(p.xs))
            for x in p.xs:
                self.pattern(x)
            self.location(p.start, p.end)
        elif k == M_VALUE:
            self.tag(TAG_VALUE_PATTERN)
            self.expr(child(p.a))
            self.location(p.start, p.end)
        elif k == M_SINGLETON:
            self.tag(TAG_SINGLETON_PATTERN)
            if p.n == 1:
                self.bool_(True)
            elif p.n == 2:
                self.bool_(False)
            else:
                self.none()
            self.location(p.start, p.end)
        elif k == M_SEQUENCE:
            self.tag(TAG_SEQUENCE_PATTERN)
            self.tagged_int(len(p.xs))
            for x in p.xs:
                self.pattern(x)
            self.location(p.start, p.end)
        elif k == M_STAR:
            self.tag(TAG_STARRED_PATTERN)
            if p.flag:
                self.bool_(True)
                self.str_(p.s)
                self.location(p.nstart, p.nend)
            else:
                self.bool_(False)
            self.location(p.start, p.end)
        elif k == M_MAPPING:
            self.tag(TAG_MAPPING_PATTERN)
            self.tagged_int(len(p.xs))
            for i in range(len(p.xs)):
                self.expr(p.xs[i])
                self.pattern(p.ys[i])
            if p.flag:
                self.bool_(True)
                self.str_(p.s)
                self.location(p.nstart, p.nend)
            else:
                self.bool_(False)
            self.location(p.start, p.end)
        elif k == M_CLASS:
            self.tag(TAG_CLASS_PATTERN)
            self.expr(child(p.a))
            self.tagged_int(len(p.xs))
            for x in p.xs:
                self.pattern(x)
            self.tagged_int(len(p.ys))
            for kw in p.ys:
                self.str_(kw.s)
                self.pattern(child(kw.a))
            self.location(p.start, p.end)
        else:
            raise ValueError("unsupported pattern")
        self.end()

    # -- types
    def invalid_type(self, note: bytes, has_note: bool) -> None:
        self.tag(TAG_RAW_EXPRESSION_TYPE)
        self.str_(b"typing.Any")
        self.none()
        if self.cv >= CV_RAW_EXPRESSION_TYPE_NOTES:
            if has_note:
                self.str_(note)
            else:
                self.none()

    def invalid_type_str(self, original: bytes, fallback: bytes) -> None:
        self.tag(TAG_RAW_EXPRESSION_TYPE)
        self.str_(fallback)
        self.str_(original)

    def type_in_list(self, t: Node) -> None:
        if t.kind == E_CALL:
            args = child(t.b)
            self.tag(TAG_CALL_TYPE)
            self.type_(child(t.a))
            self.tag(TAG_LIST_GEN)
            self.int_(len(args.xs))
            for a in args.xs:
                self.type_(a)
            self.tag(TAG_LIST_GEN)
            self.int_(len(args.ys))
            for kw in args.ys:
                if kw.flag:
                    self.str_(kw.s)
                else:
                    self.none()
                self.type_(child(kw.a))
            self.location(t.start, t.end)
            self.end()
            return
        self.type_(t)

    def type_(self, t: Node) -> None:
        k = t.kind
        if k == E_NAME:
            self.simple_unbound_type(t.s, b"", False)
        elif k == E_ATTRIBUTE:
            self.attribute_type(t, b"", False)
        elif k == E_SUBSCRIPT:
            self.subscript_type(t, b"", False)
        elif k == E_NONE:
            self.simple_unbound_type(b"None", b"", False)
        elif k == E_BOOL:
            self.tag(TAG_RAW_EXPRESSION_TYPE)
            self.str_(b"builtins.bool")
            self.bool_(t.flag)
        elif k == E_INT:
            if t.flag:
                self.tag(TAG_RAW_EXPRESSION_TYPE)
                self.str_(b"builtins.int")
                self.tagged_int(t.ival)
            else:
                self.invalid_type(b"", False)
        elif k == E_FLOAT or k == E_COMPLEX:
            self.invalid_type(b"", False)
        elif k == E_BINOP:
            if t.n == 9:
                self.union_type(t, t.start, t.end, b"", False)
                return
            self.invalid_type(b"", False)
        elif k == E_LIST:
            self.tag(TAG_LIST_TYPE)
            self.tag(TAG_LIST_GEN)
            self.int_(len(t.xs))
            for item in t.xs:
                self.type_in_list(item)
        elif k == E_TUPLE:
            self.tag(TAG_TUPLE_TYPE)
            self.tag(TAG_LIST_GEN)
            self.int_(len(t.xs))
            for item in t.xs:
                self.type_(item)
            self.bool_(True)
        elif k == E_DICT:
            ok = len(t.xs) > 0
            for item in t.xs:
                if item.a is not None and item.a.kind != E_STRING:
                    ok = False
            if ok:
                self.tag(TAG_TYPED_DICT_TYPE)
                self.tag(TAG_LIST_GEN)
                self.int_(len(t.xs))
                for item in t.xs:
                    key = item.a
                    if key is not None:
                        total = 0
                        for part in key.xs:
                            total += len(part.s)
                        self.out.append(BYTE[TAG_LITERAL_STR])
                        self.int_(total)
                        for part in key.xs:
                            self.out.append(part.s)
                    else:
                        self.none()
                self.tag(TAG_LIST_GEN)
                self.int_(len(t.xs))
                for item in t.xs:
                    self.type_(child(item.b))
            else:
                self.invalid_type(b"", False)
        elif k == E_CALL:
            name = qualified_name(child(t.a))
            if name is not None:
                args = child(t.b)
                if len(args.ys) == 0:
                    note = b"Suggestion: use " + name + b"[...] instead of " + name + b"(...)"
                else:
                    note = b"Cannot use a function call in a type annotation"
                self.invalid_type(note, True)
            else:
                self.invalid_type(b"", False)
        elif k == E_ELLIPSIS:
            self.tag(TAG_ELLIPSIS_TYPE)
        elif k == E_STARRED:
            self.tag(TAG_UNPACK_TYPE)
            self.type_(child(t.a))
            self.bool_(True)
        elif k == E_UNARYOP:
            if t.n == 3:
                v = int_literal_value(t)
                if v is not None:
                    self.tag(TAG_RAW_EXPRESSION_TYPE)
                    self.str_(b"builtins.int")
                    self.tagged_int(v)
                    self.location(t.start, t.end)
                    self.end()
                    return
                self.invalid_type(b"", False)
            elif t.n == 2:
                v = int_literal_value(child(t.a))
                if v is not None:
                    self.tag(TAG_RAW_EXPRESSION_TYPE)
                    self.str_(b"builtins.int")
                    self.tagged_int(v)
                    self.location(t.start, t.end)
                    self.end()
                    return
                self.invalid_type(b"", False)
            else:
                self.invalid_type(b"", False)
        elif k == E_STRING:
            value = b"".join([part.s for part in t.xs])
            was = self.is_evaluated
            self.is_evaluated = False
            self.string_type(value, t.start, t.end)
            self.is_evaluated = was
            return
        elif k == E_BYTES:
            self.tag(TAG_RAW_EXPRESSION_TYPE)
            self.str_(b"builtins.bytes")
            self.str_(bytes_escaped(t))
        else:
            self.invalid_type(b"", False)
        self.location(t.start, t.end)
        self.end()

    def string_type(self, value: bytes, start: int, end: int) -> None:
        p = Parser(b"(" + value + b")", MODE_EXPRESSION)
        e = p.parse_single_expression()
        if len(p.err_start) == 0:
            k = e.kind
            if k == E_NAME:
                self.simple_unbound_type(e.s, value, True)
                self.location(start, end)
                self.end()
                return
            if k == E_ATTRIBUTE:
                self.attribute_type(e, value, True)
                self.location(start, end)
                self.end()
                return
            if k == E_SUBSCRIPT:
                relocate(child(e.b), start, end)
                self.subscript_type(e, value, True)
                self.location(start, end)
                self.end()
                return
            if k == E_BINOP and e.n == 9:
                relocate(child(e.a), start, end)
                relocate(child(e.b), start, end)
                self.union_type(e, start, end, value, True)
                return
            if k == E_NONE:
                self.simple_unbound_type(b"None", value, True)
                self.location(start, end)
                self.end()
                return
        self.tag(TAG_RAW_EXPRESSION_TYPE)
        self.str_(b"builtins.str")
        self.str_(value)
        self.location(start, end)
        self.end()

    def union_type(self, b: Node, start: int, end: int, original: bytes, has_original: bool) -> None:
        self.tag(TAG_UNION_TYPE)
        self.tag(TAG_LIST_GEN)
        self.int_(2)
        self.type_(child(b.a))
        self.type_(child(b.b))
        self.bool_(True)
        self.original_str(original, has_original)
        self.bool_(self.is_evaluated)
        self.location(start, end)
        self.end()

    def original_str(self, original: bytes, has_original: bool) -> None:
        if has_original:
            self.str_(original)
            self.str_(b"builtins.str")
        else:
            self.none()
            self.none()

    def attribute_type(self, e: Node, original: bytes, has_original: bool) -> None:
        name = qualified_name(e)
        if name is None:
            if has_original:
                self.invalid_type_str(original, b"builtins.str")
            else:
                self.invalid_type(b"", False)
            return
        self.tag(TAG_UNBOUND_TYPE)
        self.str_(name)
        self.tag(TAG_LIST_GEN)
        self.int_(0)
        self.bool_(False)
        self.original_str(original, has_original)

    def subscript_type(self, e: Node, original: bytes, has_original: bool) -> None:
        name = qualified_name(child(e.a))
        if name is None:
            if has_original:
                self.invalid_type_str(original, b"builtins.str")
            else:
                self.invalid_type(b"", False)
            return
        self.tag(TAG_UNBOUND_TYPE)
        self.str_(name)
        self.tag(TAG_LIST_GEN)
        sl = child(e.b)
        if sl.kind == E_TUPLE:
            self.int_(len(sl.xs))
            for item in sl.xs:
                self.type_(item)
            self.bool_(len(sl.xs) == 0)
        else:
            self.int_(1)
            self.type_(sl)
            self.bool_(False)
        self.original_str(original, has_original)

    def simple_unbound_type(self, name: bytes, original: bytes, has_original: bool) -> None:
        self.tag(TAG_UNBOUND_TYPE)
        self.str_(name)
        self.tag(TAG_LIST_GEN)
        self.int_(0)
        self.bool_(False)
        self.original_str(original, has_original)


def char_tail(lead: int) -> int:
    # continuation bytes after a UTF-8 lead byte
    if lead < 0xE0:
        return 1
    if lead < 0xF0:
        return 2
    return 3


def token_partition(starts: list[int], offset: int) -> int:
    # the number of tokens that start before offset
    lo = 0
    hi = len(starts)
    while lo < hi:
        mid = (lo + hi) // 2
        if starts[mid] < offset:
            lo = mid + 1
        else:
            hi = mid
    return lo


def param_count(params: Node) -> int:
    n = len(params.xs) + len(params.ys) + len(params.zs)
    if params.a is not None:
        n += 1
    if params.b is not None:
        n += 1
    return n


def all_params(params: Node) -> list[Node]:
    # the Parameter nodes in order: positional-only, positional, *args, keyword-only, **kwargs
    out: list[Node] = []
    for pd in params.xs:
        out.append(child(pd.a))
    for pd in params.ys:
        out.append(child(pd.a))
    if params.a is not None:
        out.append(params.a)
    for pd in params.zs:
        out.append(child(pd.a))
    if params.b is not None:
        out.append(params.b)
    return out


def relocate(e: Node, start: int, end: int) -> None:
    # relocate_expr: every range of the expression (and of the nodes in it) becomes start..end
    e.start = start
    e.end = end
    if e.a is not None:
        relocate(e.a, start, end)
    if e.b is not None:
        relocate(e.b, start, end)
    if e.c is not None:
        relocate(e.c, start, end)
    for x in e.xs:
        relocate(x, start, end)
    for x in e.ys:
        relocate(x, start, end)
    for x in e.zs:
        relocate(x, start, end)
    for x in e.ws:
        relocate(x, start, end)


def qualified_name(e: Node) -> bytes | None:
    if e.kind == E_NAME:
        return e.s
    if e.kind == E_ATTRIBUTE:
        base = qualified_name(child(e.a))
        if base is None:
            return None
        return base + b"." + e.s
    return None


def int_literal_value(e: Node) -> int | None:
    if e.kind == E_INT:
        if e.flag:
            return e.ival
        return None
    if e.kind == E_UNARYOP and e.n == 3:
        v = int_literal_value(child(e.a))
        if v is None:
            return None
        return -v
    return None


HEXCHARS = b"0123456789abcdef"


def bytes_escaped(e: Node) -> bytes:
    squotes = False
    dquotes = False
    for part in e.xs:
        if part.s.find(b"'") >= 0:
            squotes = True
        if part.s.find(b'"') >= 0:
            dquotes = True
    escape_quote = squotes and dquotes
    out: list[bytes] = []
    for part in e.xs:
        for c in part.s:
            if c == 13:
                out.append(b"\\r")
            elif c == 10:
                out.append(b"\\n")
            elif c == 9:
                out.append(b"\\t")
            elif c == 92:
                out.append(b"\\\\")
            elif c == 39 and escape_quote:
                out.append(b"\\'")
            elif 32 <= c <= 126:
                out.append(BYTE[c])
            else:
                out.append(bytes([92, 120, HEXCHARS[c >> 4], HEXCHARS[c & 15]]))
    return b"".join(out)


# ---------------------------------------------------------------- reachability
def name_truth(name: bytes, options: Options) -> int:
    if name == b"MYPY" or name == b"TYPE_CHECKING":
        return MYPY_TRUE
    if name == b"PY2":
        return ALWAYS_FALSE
    if name == b"PY3":
        return ALWAYS_TRUE
    if name in options.always_true:
        return ALWAYS_TRUE
    if name in options.always_false:
        return ALWAYS_FALSE
    return TRUTH_UNKNOWN


def invert(t: int) -> int:
    if t == ALWAYS_TRUE:
        return ALWAYS_FALSE
    if t == ALWAYS_FALSE:
        return ALWAYS_TRUE
    if t == MYPY_TRUE:
        return MYPY_FALSE
    if t == MYPY_FALSE:
        return MYPY_TRUE
    return TRUTH_UNKNOWN


def combine_bool_op(op: int, values: list[int]) -> int:
    has_at = ALWAYS_TRUE in values
    has_mt = MYPY_TRUE in values
    has_af = ALWAYS_FALSE in values
    has_mf = MYPY_FALSE in values
    has_unknown = TRUTH_UNKNOWN in values
    if op == 1:  # or
        if has_at:
            return ALWAYS_TRUE
        if has_mt:
            return MYPY_TRUE
        if not has_af and not has_unknown and has_mf:
            return MYPY_FALSE
        if not has_unknown and not has_at and not has_mt:
            return ALWAYS_FALSE
        return TRUTH_UNKNOWN
    if has_af:
        return ALWAYS_FALSE
    if has_mf:
        return MYPY_FALSE
    if not has_mt and not has_unknown and has_at:
        return ALWAYS_TRUE
    if not has_unknown and not has_af and not has_mf:
        return MYPY_TRUE
    return TRUTH_UNKNOWN


def is_sys_attr(e: Node, name: bytes) -> bool:
    if e.kind == E_ATTRIBUTE and e.s == name:
        v = child(e.a)
        return v.kind == E_NAME and v.s == b"sys"
    return False


I32_MIN = -2147483648
I32_MAX = 2147483647


def expr_to_int(e: Node) -> int | None:
    # (as_i32 of a non-negative literal)
    if e.kind == E_INT and e.flag and e.ival <= I32_MAX:
        return e.ival
    return None


def fixed_comparison(cmp: int, op: int) -> int:
    # cmp: -1, 0, 1 for left < = > right
    if op == 0:
        r = cmp == 0
    elif op == 1:
        r = cmp != 0
    elif op == 2:
        r = cmp < 0
    elif op == 3:
        r = cmp <= 0
    elif op == 4:
        r = cmp > 0
    elif op == 5:
        r = cmp >= 0
    else:
        return TRUTH_UNKNOWN
    return ALWAYS_TRUE if r else ALWAYS_FALSE


def compare_ints(a: list[int], b: list[int]) -> int:
    for i in range(min(len(a), len(b))):
        if a[i] < b[i]:
            return -1
        if a[i] > b[i]:
            return 1
    if len(a) < len(b):
        return -1
    if len(a) > len(b):
        return 1
    return 0


def reverse_cmp_op(op: int) -> int:
    if op == 2:
        return 4
    if op == 3:
        return 5
    if op == 4:
        return 2
    if op == 5:
        return 3
    return op


class VersionInfo:
    # kind 0 whole, 1 index, 2 slice; begin/end with has_ flags
    def __init__(self, kind: int, index: int, has_begin: bool, begin: int, has_end: bool, end: int) -> None:
        self.kind: int = kind
        self.index: int = index
        self.has_begin: bool = has_begin
        self.begin: int = begin
        self.has_end: bool = has_end
        self.end: int = end


def contains_sys_version_info(e: Node) -> VersionInfo | None:
    if is_sys_attr(e, b"version_info"):
        return VersionInfo(0, 0, False, 0, False, 0)
    if e.kind == E_SUBSCRIPT:
        if not is_sys_attr(child(e.a), b"version_info"):
            return None
        sl = child(e.b)
        if sl.kind == E_INT or sl.kind == E_FLOAT or sl.kind == E_COMPLEX:
            idx = expr_to_int(sl)
            if idx is None:
                return None
            return VersionInfo(1, idx, False, 0, False, 0)
        if sl.kind == E_SLICE:
            if sl.c is not None:
                step = expr_to_int(sl.c)
                if step is None or step != 1:
                    return None
            has_begin = False
            begin = 0
            if sl.a is not None:
                b = expr_to_int(sl.a)
                if b is None:
                    return None
                has_begin = True
                begin = b
            has_end = False
            end = 0
            if sl.b is not None:
                en = expr_to_int(sl.b)
                if en is None:
                    return None
                has_end = True
                end = en
            return VersionInfo(2, 0, has_begin, begin, has_end, end)
    return None


def int_or_tuple(e: Node) -> list[int] | None:
    # [value] for an int (marked by a leading 1), [0, values...] for a tuple of ints
    v = expr_to_int(e)
    if v is not None:
        return [1, v]
    if e.kind == E_TUPLE:
        out = [0]
        for item in e.xs:
            iv = expr_to_int(item)
            if iv is None:
                return None
            out.append(iv)
        return out
    return None


def consider_sys_version_info(e: Node, options: Options) -> int:
    if e.kind != E_COMPARE:
        return TRUTH_UNKNOWN
    if len(e.ints) > 1:
        return TRUTH_UNKNOWN
    op = e.ints[0]
    if op > 5:
        return TRUTH_UNKNOWN
    left = child(e.a)
    right = e.ys[0]
    index = contains_sys_version_info(left)
    thing = int_or_tuple(right)
    if index is None or thing is None:
        index = contains_sys_version_info(right)
        thing = int_or_tuple(left)
        op = reverse_cmp_op(op)
    if index is None or thing is None:
        return TRUTH_UNKNOWN
    major, minor = options.python_version
    if index.kind == 1 and thing[0] == 1:
        idx = index.index
        if 0 <= idx <= 1:
            comp = major if idx == 0 else minor
            value = thing[1]
            return fixed_comparison(-1 if comp < value else (1 if comp > value else 0), op)
        return TRUTH_UNKNOWN
    if thing[0] == 0:
        if index.kind == 2:
            lo = index.begin if index.has_begin else 0
            hi = index.end if index.has_end else 2
        elif index.kind == 0:
            lo = 0
            hi = 2
        else:
            return TRUTH_UNKNOWN
        if lo < 0 or hi > 2 or lo >= hi:
            return TRUTH_UNKNOWN
        if lo == 0 and hi == 1:
            version = [major]
        elif lo == 0 and hi == 2:
            version = [major, minor]
        elif lo == 1 and hi == 2:
            version = [minor]
        else:
            return TRUTH_UNKNOWN
        target = thing[1:]
        if len(version) == len(target) or (len(version) > len(target) and op != 0 and op != 1):
            return fixed_comparison(compare_ints(version, target), op)
        return TRUTH_UNKNOWN
    return TRUTH_UNKNOWN


def string_value(e: Node) -> bytes:
    return b"".join([part.s for part in e.xs])


def consider_sys_platform(e: Node, options: Options) -> int:
    platform = options.platform
    if e.kind == E_COMPARE:
        if len(e.ints) > 1:
            return TRUTH_UNKNOWN
        op = e.ints[0]
        if not is_sys_attr(child(e.a), b"platform"):
            return TRUTH_UNKNOWN
        right = e.ys[0]
        if op == 0 or op == 1:
            if right.kind == E_STRING:
                value = string_value(right)
                return fixed_comparison(0 if platform == value else (-1 if platform < value else 1), op)
        elif op == 8 or op == 9:
            if right.kind == E_TUPLE or right.kind == E_LIST or right.kind == E_SET:
                contains = False
                for item in right.xs:
                    if item.kind != E_STRING:
                        return TRUTH_UNKNOWN
                    if string_value(item) == platform:
                        contains = True
                if op == 9:
                    contains = not contains
                return ALWAYS_TRUE if contains else ALWAYS_FALSE
        return TRUTH_UNKNOWN
    if e.kind == E_CALL:
        func = child(e.a)
        if func.kind != E_ATTRIBUTE:
            return TRUTH_UNKNOWN
        args = child(e.b)
        if len(args.xs) != 1:
            return TRUTH_UNKNOWN
        if not is_sys_attr(child(func.a), b"platform"):
            return TRUTH_UNKNOWN
        if func.s != b"startswith":
            return TRUTH_UNKNOWN
        arg = args.xs[0]
        if arg.kind == E_STRING:
            if platform.startswith(string_value(arg)):
                return ALWAYS_TRUE
            return ALWAYS_FALSE
        return TRUTH_UNKNOWN
    return TRUTH_UNKNOWN


def assert_will_always_fail(s: Node, options: Options) -> bool:
    if s.kind == S_ASSERT:
        t = infer_condition_value(child(s.a), options)
        return t == ALWAYS_FALSE or t == MYPY_FALSE
    return False


def infer_condition_value(e: Node, options: Options) -> int:
    k = e.kind
    if k == E_UNARYOP and e.n == 1:
        return invert(infer_condition_value(child(e.a), options))
    if k == E_BOOL:
        if e.flag:
            return ALWAYS_TRUE if b"True" in options.always_true else TRUTH_UNKNOWN
        return ALWAYS_FALSE if b"False" in options.always_false else TRUTH_UNKNOWN
    if k == E_NAME:
        return name_truth(e.s, options)
    if k == E_ATTRIBUTE:
        return name_truth(e.s, options)
    if k == E_BOOLOP:
        values = [infer_condition_value(v, options) for v in e.xs]
        return combine_bool_op(e.n, values)
    r = consider_sys_version_info(e, options)
    if r != TRUTH_UNKNOWN:
        return r
    return consider_sys_platform(e, options)


def infer_pattern_value(p: Node) -> int:
    if p.kind == M_AS and p.a is None:
        return ALWAYS_TRUE
    if p.kind == M_OR:
        for x in p.xs:
            if infer_pattern_value(x) == ALWAYS_TRUE:
                return ALWAYS_TRUE
    return TRUTH_UNKNOWN


def false_like(t: int) -> bool:
    return t == ALWAYS_FALSE or t == MYPY_FALSE


def true_like(t: int) -> bool:
    return t == ALWAYS_TRUE or t == MYPY_TRUE


class IfAnalyzer:
    def __init__(self, options: Options) -> None:
        self.options: Options = options
        self.tail_unreachable = False
        self.seen_mypy_true = False
        self.seen_mypy_false = False

    def condition_flags(self, e: Node) -> tuple[bool, bool]:
        truth = infer_condition_value(e, self.options)
        unreachable = self.tail_unreachable or false_like(truth)
        mypy_only = not unreachable and not self.seen_mypy_true and truth == MYPY_TRUE
        self.tail_unreachable = self.tail_unreachable or true_like(truth)
        self.seen_mypy_true = self.seen_mypy_true or truth == MYPY_TRUE
        self.seen_mypy_false = self.seen_mypy_false or truth == MYPY_FALSE
        return unreachable, mypy_only

    def else_flags(self) -> tuple[bool, bool]:
        unreachable = self.tail_unreachable
        mypy_only = not unreachable and self.seen_mypy_false and not self.seen_mypy_true
        return unreachable, mypy_only

    def match_case_flags(self, pattern: Node, guard: Node | None) -> tuple[bool, bool]:
        pt = infer_pattern_value(pattern)
        gt = ALWAYS_TRUE
        if guard is not None:
            gt = infer_condition_value(guard, self.options)
        unreachable = self.tail_unreachable or false_like(pt) or false_like(gt)
        mypy_only = not unreachable and not self.seen_mypy_true and gt == MYPY_TRUE and true_like(pt)
        self.tail_unreachable = self.tail_unreachable or (true_like(gt) and true_like(pt))
        self.seen_mypy_true = self.seen_mypy_true or (gt == MYPY_TRUE and true_like(pt))
        return unreachable, mypy_only


# ---------------------------------------------------------------- function bodies
def is_trivial_body(body: list[Node]) -> bool:
    if len(body) == 0:
        return False
    i = 0
    first = body[0]
    if first.kind == S_EXPR and child(first.a).kind == E_STRING:
        i = 1
    if i == len(body):
        return True
    if len(body) > i + 1:
        return False
    s = body[i]
    if s.kind == S_PASS or s.kind == S_RAISE:
        return True
    if s.kind == S_EXPR:
        return child(s.a).kind == E_ELLIPSIS
    return False


def has_externally_visible_effect(body: list[Node], params: Node, check_attributes: bool) -> bool:
    if is_trivial_body(body):
        return True
    first = b""
    if check_attributes:
        if len(params.xs) > 0:
            first = child(params.xs[0].a).s
        elif len(params.ys) > 0:
            first = child(params.ys[0].a).s
    d = EffectDetector(first)
    for s in body:
        d.visit_stmt(s)
    return d.defines_attributes or d.contains_yield


class EffectDetector:
    def __init__(self, first_param: bytes) -> None:
        self.first_param: bytes = first_param
        self.defines_attributes = False
        self.contains_yield = False

    def contains_param_attribute(self, e: Node) -> bool:
        k = e.kind
        if k == E_ATTRIBUTE:
            v = child(e.a)
            return v.kind == E_NAME and v.s == self.first_param
        if k == E_TUPLE or k == E_LIST:
            for x in e.xs:
                if self.contains_param_attribute(x):
                    return True
            return False
        if k == E_STARRED:
            return self.contains_param_attribute(child(e.a))
        return False

    def visit_stmt(self, s: Node) -> None:
        if self.defines_attributes and self.contains_yield:
            return
        k = s.kind
        if k == S_FUNCTIONDEF or k == S_CLASSDEF:
            return
        if k == S_ASSIGN:
            for t in s.xs:
                if self.contains_param_attribute(t):
                    self.defines_attributes = True
                    return
        elif k == S_AUGASSIGN or k == S_ANNASSIGN or k == S_FOR:
            if self.contains_param_attribute(child(s.a)):
                self.defines_attributes = True
                return
        elif k == S_WITH:
            for item in s.xs:
                if item.b is not None and self.contains_param_attribute(item.b):
                    self.defines_attributes = True
                    return
        self.walk(s)

    def visit_expr(self, e: Node) -> None:
        if self.defines_attributes and self.contains_yield:
            return
        k = e.kind
        if k == E_YIELD or k == E_YIELDFROM:
            self.contains_yield = True
            return
        if k == E_LAMBDA:
            return
        self.walk(e)

    def walk(self, n: Node) -> None:
        # walk_stmt / walk_expr: every statement, expression and pattern in the node (the
        # visitor only acts on statements and expressions, so the order does not matter)
        for x in (n.a, n.b, n.c):
            if x is not None:
                self.visit_any(x)
        for x in n.xs:
            self.visit_any(x)
        for x in n.ys:
            self.visit_any(x)
        for x in n.zs:
            self.visit_any(x)
        for x in n.ws:
            self.visit_any(x)

    def visit_any(self, n: Node) -> None:
        k = n.kind
        if 40 <= k <= 64:
            self.visit_stmt(n)
        elif 1 <= k <= 35:
            self.visit_expr(n)
        else:
            self.walk(n)


# ---------------------------------------------------------------- comments
def is_rust_ws(c: int) -> bool:
    # (c a code point)
    return c == 32 or 9 <= c <= 13 or c == 0x85 or c == 0xA0 or c == 0x1680 or \
        0x2000 <= c <= 0x200A or c == 0x2028 or c == 0x2029 or c == 0x202F or c == 0x205F or c == 0x3000


def trim_start(b: bytes) -> bytes:
    i = 0
    n = len(b)
    while i < n:
        c = b[i]
        if c < 0x80:
            if c == 32 or 9 <= c <= 13:
                i += 1
                continue
            break
        w = 2 if c < 0xE0 else (3 if c < 0xF0 else 4)
        cp = ord(b[i:i + w].decode())
        if is_rust_ws(cp):
            i += w
            continue
        break
    return b[i:]


def trim_end(b: bytes) -> bytes:
    j = len(b)
    while j > 0:
        c = b[j - 1]
        if c < 0x80:
            if c == 32 or 9 <= c <= 13:
                j -= 1
                continue
            break
        k = j - 1
        while k > 0 and (b[k] & 0xC0) == 0x80:
            k -= 1
        cp = ord(b[k:j].decode())
        if is_rust_ws(cp):
            j = k
            continue
        break
    return b[:j]


def trim(b: bytes) -> bytes:
    return trim_end(trim_start(b))


def is_alnum(cp: int) -> bool:
    # char::is_alphanumeric (for ASCII exactly; above ASCII, Python's str.isalnum)
    if cp < 0x80:
        return 48 <= cp <= 57 or 65 <= cp <= 90 or 97 <= cp <= 122
    return chr(cp).isalnum()


TC_PART_NONE = 0
TC_PART_TYPE_IGNORE = 1
TC_PART_MYPY_IGNORE = 2
TC_PART_ANNOTATION = 3
TC_PART_INVALID_IGNORE = 4


class CommentPart:
    def __init__(self, kind: int, codes: list[bytes], text: bytes, is_mypy: bool) -> None:
        self.kind: int = kind
        self.codes: list[bytes] = codes
        self.text: bytes = text
        self.is_mypy: bool = is_mypy


def parse_error_codes(after_ignore: bytes) -> list[bytes] | None:
    t = trim_start(after_ignore)
    h = t.find(b"#")
    if h >= 0:
        t = t[:h]
    t = trim_end(t)
    if t.startswith(b"["):
        if not t.endswith(b"]"):
            return None
        inner = t[1:len(t) - 1]
        codes: list[bytes] = []
        for piece in inner.split(b","):
            c = trim(piece)
            if len(c) > 0:
                codes.append(c)
        for code in codes:
            for ch in code.decode():
                if not is_alnum(ord(ch)) and ch != "_" and ch != "-" and ch != ":":
                    return None
        return codes
    if len(t) > 0:
        return None
    return []


def parse_comment_part(part: bytes) -> CommentPart | None:
    trimmed = trim(part)
    mypy_comment = trimmed.startswith(b"mypy:")
    if not trimmed.startswith(b"type:") and not mypy_comment:
        return None
    after_type = trim_start(trimmed[5:])
    if after_type.startswith(b"ignore"):
        after_ignore = after_type[6:]
        ok = len(after_ignore) == 0
        if not ok:
            c = after_ignore[0]
            if c == 91:
                ok = True
            elif c < 0x80:
                ok = c == 32 or 9 <= c <= 13
            else:
                w = 2 if c < 0xE0 else (3 if c < 0xF0 else 4)
                ok = is_rust_ws(ord(after_ignore[:w].decode()))
        if ok:
            codes = parse_error_codes(after_ignore)
            if codes is None:
                return CommentPart(TC_PART_INVALID_IGNORE, [], b"", mypy_comment)
            if mypy_comment:
                return CommentPart(TC_PART_MYPY_IGNORE, codes, b"", True)
            return CommentPart(TC_PART_TYPE_IGNORE, codes, b"", False)
    if mypy_comment:
        return None
    return CommentPart(TC_PART_ANNOTATION, [], after_type, False)


def parse_type_comments_full(comment: bytes, skip_commented: bool) -> list[CommentPart]:
    parts: list[CommentPart] = []
    if not comment.startswith(b"#"):
        return parts
    ignore_next = False
    for part in comment[1:].split(b"#"):
        if len(trim(part)) == 0:
            ignore_next = True
            continue
        if ignore_next:
            ignore_next = False
            continue
        parsed = parse_comment_part(part)
        if parsed is not None:
            parts.append(parsed)
        elif skip_commented:
            break
    return parts


def parse_expression(text: bytes) -> tuple[Node, bool]:
    # (the expression, and whether it parsed without errors)
    p = Parser(text, MODE_EXPRESSION)
    e = p.parse_single_expression()
    return e, len(p.err_start) == 0


def parse_func_type_comment(comment: bytes) -> tuple[list[bytes], bytes] | None:
    p = Parser(comment, MODE_EXPRESSION)
    p.parse_single_expression()
    kinds = p.tok_kind
    starts = p.tok_start
    ends = p.tok_end
    n = len(kinds)
    i = 0
    nesting = 0
    # iter_with_context: the nesting after each token
    if n == 0 or kinds[0] != T_LPAR:
        return None
    nesting = 1
    i = 1
    if i >= n:
        return None
    arg_types: list[bytes] = []
    arg_start = starts[i]
    arg_end = arg_start
    star_stripped = False
    while True:
        if i >= n:
            return None
        k = kinds[i]
        ts = starts[i]
        te = ends[i]
        i += 1
        if k == T_LPAR or k == T_LBRACE or k == T_LSQB:
            nesting += 1
        elif k == T_RPAR or k == T_RBRACE or k == T_RSQB:
            if nesting > 0:
                nesting -= 1
        elif k == T_NEWLINE and nesting > 0:
            nesting = 0
        if k == T_COMMA and nesting == 1:
            arg_types.append(comment[arg_start:arg_end])
            if i >= n:
                return None
            arg_start = starts[i]
            arg_end = arg_start
            star_stripped = False
        elif (k == T_STAR or k == T_DOUBLESTAR) and nesting == 1:
            if star_stripped:
                return None
            if arg_start == ts:
                if i >= n:
                    return None
                arg_start = starts[i]
                arg_end = arg_start
                star_stripped = True
        elif k == T_RPAR and nesting == 0:
            if arg_end != arg_start:
                arg_types.append(comment[arg_start:arg_end])
            break
        else:
            arg_end = te
    if i >= n or kinds[i] != T_RARROW:
        return None
    i += 1
    if i >= n:
        return None
    return arg_types, comment[starts[i]:]


def function_comment_to_expr(arg_types: list[bytes], ret_type: bytes) -> TypeComment | None:
    args: list[Node] = []
    for a in arg_types:
        e, ok = parse_expression(b"(" + a + b")")
        if not ok:
            return None
        args.append(e)
    r, ok = parse_expression(b"(" + ret_type + b")")
    if not ok:
        return None
    return TypeComment(TC_FUNCTION, r, args, "")


class CommentResults:
    def __init__(self) -> None:
        self.type_ignores: list[tuple[int, list[bytes]]] = []
        self.mypy_ignores: list[tuple[int, list[bytes]]] = []
        self.type_comments: dict[int, TypeComment] = {}
        self.mypy_comments: list[tuple[int, bytes]] = []
        self.errors: list[SyntaxError_] = []


def extract_type_comments_and_ignores(p: Parser, text: bytes, li: LineIndex, options: Options) -> CommentResults:
    r = CommentResults()
    kinds = p.tok_kind
    starts = p.tok_start
    ends = p.tok_end
    for idx in range(len(kinds)):
        if kinds[idx] != T_COMMENT:
            continue
        cs = starts[idx]
        comment = text[cs:ends[idx]]
        line = li.line_of(cs)
        column = li.column(line, cs)
        if column == 1 and comment.startswith(b"# mypy:"):
            t = trim(comment[7:])
            if len(t) > 0:
                is_ignore = t == b"ignore" or t.startswith(b"ignore[") or t.startswith(b"ignore ")
                if not is_ignore:
                    r.mypy_comments.append((line, t))
        before = text[li.line_start(line):cs]
        skip_commented = len(trim(before)) == 0 or options.cache_version < CV_FULL_TYPE_COMMENTS
        parts = parse_type_comments_full(comment, skip_commented)
        seen_type_ignore = False
        seen_mypy_ignore = False
        for part in parts:
            if part.kind == TC_PART_INVALID_IGNORE:
                msg = 'Invalid "mypy: ignore" comment' if part.is_mypy else 'Invalid "type: ignore" comment'
                r.errors.append(SyntaxError_(line, column, msg, False))
            elif part.kind == TC_PART_TYPE_IGNORE:
                if seen_type_ignore:
                    r.errors.append(SyntaxError_(line, column, "Multiple type ignores on the same line", False))
                    continue
                r.type_ignores.append((line, part.codes))
                seen_type_ignore = True
            elif part.kind == TC_PART_MYPY_IGNORE:
                if seen_mypy_ignore:
                    r.errors.append(SyntaxError_(line, column, "Multiple mypy ignores on the same line", False))
                    continue
                r.mypy_ignores.append((line, part.codes))
                seen_mypy_ignore = True
            else:
                if line in r.type_comments:
                    r.errors.append(SyntaxError_(line, column, "Multiple type comments on the same line", False))
                    continue
                annotation = part.text
                if len(annotation) == 0:
                    r.type_comments[line] = TypeComment(TC_INVALID, None, [], 'Syntax error in type comment ""')
                    continue
                e, ok = parse_expression(b"(" + annotation + b")")
                if ok:
                    r.type_comments[line] = TypeComment(TC_REGULAR, e, [], "")
                    continue
                fc = parse_func_type_comment(annotation)
                if fc is not None:
                    tc = function_comment_to_expr(fc[0], fc[1])
                    if tc is not None:
                        r.type_comments[line] = tc
                        continue
                r.type_comments[line] = TypeComment(TC_INVALID, None, [],
                                                    'Syntax error in type comment "' + annotation.decode() + '"')
    return r


# ---------------------------------------------------------------- inline configuration
def split_respecting_quotes(s: bytes) -> list[bytes]:
    parts: list[bytes] = []
    current: list[int] = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        i += 1
        if c == 44:
            parts.append(bytes(current))
            current = []
        elif c == 34:
            while i < n:
                c2 = s[i]
                i += 1
                if c2 == 34:
                    break
                current.append(c2)
        else:
            current.append(c)
    parts.append(bytes(current))
    return parts


def parse_bool(s: bytes) -> int:
    # 1 true, 0 false, -1 not a configparser bool
    low = s.decode().lower()
    if low == "1" or low == "yes" or low == "true" or low == "on":
        return 1
    if low == "0" or low == "no" or low == "false" or low == "off":
        return 0
    return -1


class InlineOverrides:
    def __init__(self) -> None:
        self.always_true: list[bytes] = []
        self.always_false: list[bytes] = []
        self.ignore_errors = -1


def resolve_overrides(comments: list[tuple[int, bytes]]) -> InlineOverrides:
    result = InlineOverrides()
    for _, text in comments:
        for part in split_respecting_quotes(text):
            t = trim(part)
            if len(t) == 0:
                continue
            eq = t.find(b"=")
            if eq >= 0:
                key = trim(t[:eq])
                value = trim(t[eq + 1:])
            else:
                key = t
                value = b"True"
            key = key.replace(b"-", b"_")
            if key == b"always_true" or key == b"always_false":
                for name in value.split(b","):
                    nm = trim(name)
                    if len(nm) > 0:
                        if key == b"always_true":
                            result.always_true.append(nm)
                        else:
                            result.always_false.append(nm)
            elif key == b"ignore_errors":
                b = parse_bool(value)
                if b >= 0:
                    result.ignore_errors = b
    return result


# ---------------------------------------------------------------- imports metadata
def serialize_imports(imports: list[ImportInfo], text: bytes, li: LineIndex) -> bytes:
    ser = Serializer(text, li, Options((3, 12), "linux", [], [], 7), False, None, {})
    ser.tag(TAG_LIST_GEN)
    ser.int_(len(imports))
    for imp in imports:
        if imp.kind == 0:
            ser.tag(TAG_IMPORT_METADATA)
            ser.str_(imp.name)
            ser.tagged_int(imp.relative)
            if imp.has_as:
                ser.bool_(True)
                ser.str_(imp.as_name)
            else:
                ser.bool_(False)
        elif imp.kind == 1:
            ser.tag(TAG_IMPORTFROM_METADATA)
            ser.str_(imp.name)
            ser.tagged_int(imp.relative)
            ser.tag(TAG_LIST_GEN)
            ser.int_(len(imp.names))
            for i in range(len(imp.names)):
                ser.str_(imp.names[i])
                if imp.has_as_names[i]:
                    ser.bool_(True)
                    ser.str_(imp.as_names[i])
                else:
                    ser.bool_(False)
        else:
            ser.tag(TAG_IMPORTALL_METADATA)
            ser.str_(imp.name)
            ser.tagged_int(imp.relative)
        ser.location(imp.start, imp.end)
        ser.tagged_int(imp.flags)
    return ser.getvalue()
