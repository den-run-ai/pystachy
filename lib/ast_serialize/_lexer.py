"""The lexer: Ruff's ruff_python_parser lexer (lexer.rs and lexer/*.rs of ast_serialize 0.13.1's
vendored crates, MIT; see THIRD_PARTY_NOTICES) over the UTF-8 bytes of the source.

Offsets are byte offsets, as Ruff's TextSize. The parser drives the lexer one token at a time
(next_token), with checkpoints to look ahead and rewind, and asks it to re-lex in error recovery.
"""
from ._tokens import (
    T_AMPER, T_AMPEREQUAL, T_AND, T_AS, T_ASSERT, T_ASYNC, T_AT, T_ATEQUAL, T_AWAIT, T_BREAK,
    T_CASE, T_CIRCUMFLEX, T_CIRCUMFLEXEQUAL, T_CLASS, T_COLON, T_COLONEQUAL, T_COMMA, T_COMMENT,
    T_COMPLEX, T_CONTINUE, T_DEDENT, T_DEF, T_DEL, T_DOT, T_DOUBLESLASH, T_DOUBLESLASHEQUAL,
    T_DOUBLESTAR, T_DOUBLESTAREQUAL, T_ELIF, T_ELLIPSIS, T_ELSE, T_ENDOFFILE, T_EQEQUAL, T_EQUAL,
    T_EXCEPT, T_EXCLAMATION, T_FALSE, T_FINALLY, T_FLOAT, T_FOR, T_FROM, T_FSTRINGEND,
    T_FSTRINGMIDDLE, T_FSTRINGSTART, T_GLOBAL, T_GREATER, T_GREATEREQUAL, T_IF, T_IMPORT, T_IN,
    T_INDENT, T_INT, T_IS, T_LAMBDA, T_LAZY, T_LBRACE, T_LEFTSHIFT, T_LEFTSHIFTEQUAL, T_LESS,
    T_LESSEQUAL, T_LPAR, T_LSQB, T_MATCH, T_MINUS, T_MINUSEQUAL, T_NAME, T_NEWLINE, T_NONE,
    T_NONLOCAL, T_NONLOGICALNEWLINE, T_NOT, T_NOTEQUAL, T_OR, T_PASS, T_PERCENT, T_PERCENTEQUAL,
    T_PLUS, T_PLUSEQUAL, T_RAISE, T_RARROW, T_RBRACE, T_RETURN, T_RIGHTSHIFT, T_RIGHTSHIFTEQUAL,
    T_RPAR, T_RSQB, T_SEMI, T_SLASH, T_SLASHEQUAL, T_STAR, T_STAREQUAL, T_STRING, T_TILDE,
    T_TRUE, T_TRY, T_TSTRINGEND, T_TSTRINGMIDDLE, T_TSTRINGSTART, T_TYPE, T_UNKNOWN, T_VBAR,
    T_VBAREQUAL, T_WHILE, T_WITH, T_YIELD,
)
from ._unicode import is_xid_continue, is_xid_start

# TokenFlags
F_DOUBLE_QUOTES = 1
F_TRIPLE_QUOTED = 2
F_UNICODE = 4
F_BYTE = 8
F_FSTRING = 16
F_TSTRING = 32
F_RAW_LOWER = 64
F_RAW_UPPER = 128
F_UNCLOSED = 256
F_NON_ASCII_NAME = 512
F_RAW = 192

# Lexer states
S_AFTER_NEWLINE = 0
S_NON_EMPTY_LOGICAL_LINE = 1
S_AFTER_EQUAL = 2
S_OTHER = 3

# Modes
MODE_MODULE = 0
MODE_EXPRESSION = 1
MODE_PARENTHESIZED_EXPRESSION = 2

MSG_UNCLOSED_STRING = "missing closing quote in string literal"
MSG_INDENTATION = "unindent does not match any outer indentation level"
MSG_LINE_CONTINUATION = "Expected a newline after line continuation character"
MSG_EOF = "unexpected EOF while parsing"

KEYWORDS: dict[bytes, int] = {
    b"False": T_FALSE, b"None": T_NONE, b"True": T_TRUE, b"and": T_AND, b"as": T_AS,
    b"assert": T_ASSERT, b"async": T_ASYNC, b"await": T_AWAIT, b"break": T_BREAK,
    b"case": T_CASE, b"class": T_CLASS, b"continue": T_CONTINUE, b"def": T_DEF, b"del": T_DEL,
    b"elif": T_ELIF, b"else": T_ELSE, b"except": T_EXCEPT, b"finally": T_FINALLY, b"for": T_FOR,
    b"from": T_FROM, b"global": T_GLOBAL, b"if": T_IF, b"import": T_IMPORT, b"in": T_IN,
    b"is": T_IS, b"lazy": T_LAZY, b"lambda": T_LAMBDA, b"match": T_MATCH,
    b"nonlocal": T_NONLOCAL, b"not": T_NOT, b"or": T_OR, b"pass": T_PASS, b"raise": T_RAISE,
    b"return": T_RETURN, b"try": T_TRY, b"type": T_TYPE, b"while": T_WHILE, b"with": T_WITH,
    b"yield": T_YIELD,
}


def _ident_table() -> list[bool]:
    t = [False] * 256
    for c in range(48, 58):
        t[c] = True
    for c in range(65, 91):
        t[c] = True
    for c in range(97, 123):
        t[c] = True
    t[95] = True
    return t


# ASCII identifier characters (letters, digits, underscore)
IDENT: list[bool] = _ident_table()


def _keyword_first_table() -> list[bool]:
    # by byte value: whether a keyword of KEYWORDS starts with it
    t = [False] * 256
    for k in KEYWORDS:
        t[k[0]] = True
    return t


KEYWORD_FIRST: list[bool] = _keyword_first_table()


def char_width(b: int) -> int:
    # the length of the UTF-8 sequence whose first byte is b
    if b < 0x80:
        return 1
    if b < 0xE0:
        return 2
    if b < 0xF0:
        return 3
    return 4


def decode_char(src: bytes, i: int) -> int:
    # the code point of the UTF-8 sequence at i (the source is valid UTF-8)
    b = src[i]
    if b < 0x80:
        return b
    if b < 0xE0:
        return ((b & 0x1F) << 6) | (src[i + 1] & 0x3F)
    if b < 0xF0:
        return ((b & 0x0F) << 12) | ((src[i + 1] & 0x3F) << 6) | (src[i + 2] & 0x3F)
    return ((b & 0x07) << 18) | ((src[i + 1] & 0x3F) << 12) | ((src[i + 2] & 0x3F) << 6) | (src[i + 3] & 0x3F)


class FStringContext:
    # lexer/interpolated_string.rs's InterpolatedStringContext
    def __init__(self, flags: int, nesting: int, spec_depth: int) -> None:
        self.flags: int = flags
        self.nesting: int = nesting
        self.spec_depth: int = spec_depth

    def copy(self) -> "FStringContext":
        return FStringContext(self.flags, self.nesting, self.spec_depth)

    def quote(self) -> int:
        return 34 if self.flags & F_DOUBLE_QUOTES else 39

    def is_triple(self) -> bool:
        return self.flags & F_TRIPLE_QUOTED != 0

    def in_interpolation(self, nesting: int) -> bool:
        open_parens = nesting - self.nesting
        if open_parens < 0:
            open_parens = 0
        return open_parens > self.spec_depth

    def in_format_spec(self, nesting: int) -> bool:
        return self.spec_depth > 0 and not self.in_interpolation(nesting)

    def try_start_format_spec(self, nesting: int) -> bool:
        open_parens = nesting - self.nesting
        if open_parens < 0:
            open_parens = 0
        d = open_parens - self.spec_depth
        if d < 0:
            d = 0
        if d == 1:
            self.spec_depth += 1
            return True
        return False

    def try_end_format_spec(self, nesting: int) -> None:
        if self.in_format_spec(nesting):
            if self.spec_depth > 0:
                self.spec_depth -= 1


class LexerCheckpoint:
    def __init__(self, kind: int, start: int, end: int, flags: int, pos: int, state: int,
                 nesting: int, cols: list[int], chars: list[int], has_pending: bool,
                 pending_col: int, pending_char: int, fstrings: list[FStringContext],
                 nerrors: int) -> None:
        self.kind: int = kind
        self.start: int = start
        self.end: int = end
        self.flags: int = flags
        self.pos: int = pos
        self.state: int = state
        self.nesting: int = nesting
        self.cols: list[int] = cols
        self.chars: list[int] = chars
        self.has_pending: bool = has_pending
        self.pending_col: int = pending_col
        self.pending_char: int = pending_char
        self.fstrings: list[FStringContext] = fstrings
        self.nerrors: int = nerrors


class Lexer:
    def __init__(self, src: bytes, mode: int, start_offset: int) -> None:
        self.src: bytes = src
        self.n: int = len(src)
        self.mode: int = mode
        self.pos: int = 0
        self.tok: int = 0  # where the token being lexed starts (Cursor::start_token)
        self.kind: int = T_ENDOFFILE
        self.start: int = start_offset
        self.end: int = start_offset
        self.flags = 0
        self.state: int = S_AFTER_NEWLINE
        self.nesting: int = 0
        if mode == MODE_PARENTHESIZED_EXPRESSION:
            self.state = S_OTHER
            self.nesting = 1
        # the indentation stack: columns (tabs to multiples of 2) and characters
        self.cols: list[int] = []
        self.chars: list[int] = []
        self.has_pending: bool = False
        self.pending_col: int = 0
        self.pending_char: int = 0
        self.fstrings: list[FStringContext] = []
        self.err_start: list[int] = []
        self.err_end: list[int] = []
        self.err_msg: list[str] = []
        if start_offset == 0:
            if self.n >= 3 and src[0] == 0xEF and src[1] == 0xBB and src[2] == 0xBF:
                self.pos = 3
        else:
            self.pos = start_offset

    # -- the cursor
    def first(self) -> int:
        return self.src[self.pos] if self.pos < self.n else 0

    def second(self) -> int:
        # the byte after the first character (an ASCII character is all this is compared to)
        p = self.pos
        if p >= self.n:
            return 0
        p += char_width(self.src[p])
        return self.src[p] if p < self.n else 0

    def bump(self) -> None:
        if self.pos < self.n:
            self.pos += char_width(self.src[self.pos])

    def eat(self, c: int) -> bool:
        if self.pos < self.n and self.src[self.pos] == c:
            self.pos += 1
            return True
        return False

    def eat2(self, c1: int, c2: int) -> bool:
        p = self.pos
        if p + 1 < self.n and self.src[p] == c1 and self.src[p + 1] == c2:
            self.pos = p + 2
            return True
        return False

    def eat3(self, c1: int, c2: int, c3: int) -> bool:
        p = self.pos
        if p + 2 < self.n and self.src[p] == c1 and self.src[p + 1] == c2 and self.src[p + 2] == c3:
            self.pos = p + 3
            return True
        return False

    def push_error(self, msg: str, start: int, end: int) -> int:
        self.start = start
        self.end = end
        self.err_start.append(start)
        self.err_end.append(end)
        self.err_msg.append(msg)
        return T_UNKNOWN

    def error_here(self, msg: str) -> int:
        return self.push_error(msg, self.tok, self.pos)

    # -- tokens
    def next_token(self) -> int:
        self.flags = 0
        kind = self.lex_token()
        self.kind = kind
        if kind != T_UNKNOWN:
            self.start = self.tok
            self.end = self.pos
        return kind

    def lex_token(self) -> int:
        if len(self.fstrings) > 0:
            fs = self.fstrings[-1]
            if not fs.in_interpolation(self.nesting):
                self.tok = self.pos
                kind = self.lex_fstring_middle_or_end()
                if kind >= 0:
                    if kind == T_FSTRINGEND or kind == T_TSTRINGEND:
                        self.fstrings.pop()
                    return kind
        elif self.has_pending:
            self.has_pending = False
            self.tok = self.pos
            cmp = self.compare_indent(self.cur_col(), self.cur_char(), self.pending_col, self.pending_char)
            if cmp == 1:
                self.has_pending = True
                if not self.dedent_one(self.pending_col, self.pending_char):
                    return self.error_here(MSG_INDENTATION)
                return T_DEDENT
            if cmp == 2:
                return self.error_here(MSG_INDENTATION)
        if self.state == S_AFTER_NEWLINE:
            self.tok = self.pos
            ind = self.eat_indentation()
            if ind >= 0:
                return ind
        else:
            p = self.pos
            if p < self.n:
                c = self.src[p]
                if c == 32 or c == 9 or c == 92 or c == 12:
                    if not self.skip_whitespace():
                        return T_UNKNOWN
        self.tok = self.pos
        if self.pos >= self.n:
            return self.consume_end()
        c = self.src[self.pos]
        if c < 0x80:
            self.pos += 1
            return self.consume_ascii(c)
        cp = decode_char(self.src, self.pos)
        self.pos += char_width(c)
        if is_xid_start(cp):
            kind = self.lex_identifier(cp)
            self.state = S_OTHER
            return kind
        return self.error_here("Got unexpected token " + chr(cp))

    # -- indentation
    def cur_col(self) -> int:
        return self.cols[-1] if len(self.cols) > 0 else 0

    def cur_char(self) -> int:
        return self.chars[-1] if len(self.chars) > 0 else 0

    def compare_indent(self, col: int, char: int, ocol: int, ochar: int) -> int:
        # Indentation::try_compare: 0 equal, 1 greater, -1 less, 2 an inconsistent mix
        c1 = 0 if col == ocol else (1 if col > ocol else -1)
        c2 = 0 if char == ochar else (1 if char > ochar else -1)
        if c1 != c2:
            return 2
        return c1

    def dedent_one(self, col: int, char: int) -> bool:
        if len(self.cols) > 0:
            self.cols.pop()
            self.chars.pop()
        cmp = self.compare_indent(col, char, self.cur_col(), self.cur_char())
        return cmp == -1 or cmp == 0

    def eat_indentation(self) -> int:
        col = 0
        char = 0
        src = self.src
        n = self.n
        while True:
            c = src[self.pos] if self.pos < n else 0
            if c == 32:
                self.pos += 1
                col += 1
                char += 1
            elif c == 9:
                self.pos += 1
                char += 1
                col += 2 - col % 2
            elif c == 92:
                self.pos += 1
                if self.eat(13):
                    self.eat(10)
                elif not self.eat(10):
                    return self.push_error(MSG_LINE_CONTINUATION, self.pos - 1, self.pos)
                if self.pos >= n:
                    return self.error_here(MSG_EOF)
                if col != 0 or char != 0:
                    while self.pos < n and (src[self.pos] == 32 or src[self.pos] == 9 or src[self.pos] == 12):
                        self.pos += 1
            elif c == 12:
                self.pos += 1
                col = 0
                char = 0
            else:
                break
        c = src[self.pos] if self.pos < n else 0
        if c != 10 and c != 13 and c != 35 and c != 0:
            self.state = S_NON_EMPTY_LOGICAL_LINE
            return self.handle_indentation(col, char)
        return -1

    def handle_indentation(self, col: int, char: int) -> int:
        cmp = self.compare_indent(self.cur_col(), self.cur_char(), col, char)
        if cmp == 1:
            self.has_pending = True
            self.pending_col = col
            self.pending_char = char
            if not self.dedent_one(col, char):
                return self.error_here(MSG_INDENTATION)
            self.tok = self.pos
            return T_DEDENT
        if cmp == 0:
            return -1
        if cmp == -1:
            self.cols.append(col)
            self.chars.append(char)
            return T_INDENT
        return self.error_here(MSG_INDENTATION)

    def skip_whitespace(self) -> bool:
        ws_start = self.pos
        src = self.src
        n = self.n
        while self.pos < n:
            c = src[self.pos]
            if c == 32 or c == 9 or c == 12:
                self.pos += 1
            elif c == 92:
                self.pos += 1
                if self.eat(13):
                    self.eat(10)
                elif not self.eat(10):
                    self.push_error(MSG_LINE_CONTINUATION, self.pos - 1, self.pos)
                    return False
                if self.pos >= n:
                    self.push_error(MSG_EOF, ws_start, self.pos)
                    return False
            else:
                break
        return True

    # -- characters
    def consume_ascii(self, c: int) -> int:
        kind = T_UNKNOWN
        if IDENT[c] and not (48 <= c <= 57):
            kind = self.lex_identifier(c)
        elif 48 <= c <= 57:
            kind = self.lex_number(c)
        elif c == 35:  # '#'
            return self.lex_comment()
        elif c == 39 or c == 34:
            kind = self.lex_string(c)
        elif c == 61:  # '='
            if self.eat(61):
                kind = T_EQEQUAL
            else:
                self.state = S_AFTER_EQUAL
                return T_EQUAL
        elif c == 43:  # '+'
            kind = T_PLUSEQUAL if self.eat(61) else T_PLUS
        elif c == 42:  # '*'
            if self.eat(61):
                kind = T_STAREQUAL
            elif self.eat(42):
                kind = T_DOUBLESTAREQUAL if self.eat(61) else T_DOUBLESTAR
            else:
                kind = T_STAR
        elif c == 47:  # '/'
            if self.eat(61):
                kind = T_SLASHEQUAL
            elif self.eat(47):
                kind = T_DOUBLESLASHEQUAL if self.eat(61) else T_DOUBLESLASH
            else:
                kind = T_SLASH
        elif c == 37:  # '%'
            kind = T_PERCENTEQUAL if self.eat(61) else T_PERCENT
        elif c == 124:  # '|'
            kind = T_VBAREQUAL if self.eat(61) else T_VBAR
        elif c == 94:  # '^'
            kind = T_CIRCUMFLEXEQUAL if self.eat(61) else T_CIRCUMFLEX
        elif c == 38:  # '&'
            kind = T_AMPEREQUAL if self.eat(61) else T_AMPER
        elif c == 45:  # '-'
            if self.eat(61):
                kind = T_MINUSEQUAL
            elif self.eat(62):
                kind = T_RARROW
            else:
                kind = T_MINUS
        elif c == 64:  # '@'
            kind = T_ATEQUAL if self.eat(61) else T_AT
        elif c == 33:  # '!'
            kind = T_NOTEQUAL if self.eat(61) else T_EXCLAMATION
        elif c == 126:
            kind = T_TILDE
        elif c == 40:
            self.nesting += 1
            kind = T_LPAR
        elif c == 41:
            if self.nesting > 0:
                self.nesting -= 1
            kind = T_RPAR
        elif c == 91:
            self.nesting += 1
            kind = T_LSQB
        elif c == 93:
            if self.nesting > 0:
                self.nesting -= 1
            kind = T_RSQB
        elif c == 123:
            self.nesting += 1
            kind = T_LBRACE
        elif c == 125:
            if len(self.fstrings) > 0:
                fs = self.fstrings[-1]
                if fs.nesting == self.nesting:
                    prefix = "f-string: " if fs.flags & F_FSTRING else "t-string: "
                    return self.error_here(prefix + "single `}` is not allowed")
                fs.try_end_format_spec(self.nesting)
            if self.nesting > 0:
                self.nesting -= 1
            kind = T_RBRACE
        elif c == 58:  # ':'
            if len(self.fstrings) > 0 and self.fstrings[-1].try_start_format_spec(self.nesting):
                kind = T_COLON
            elif self.eat(61):
                kind = T_COLONEQUAL
            else:
                kind = T_COLON
        elif c == 59:
            kind = T_SEMI
        elif c == 60:  # '<'
            if self.eat(60):
                kind = T_LEFTSHIFTEQUAL if self.eat(61) else T_LEFTSHIFT
            elif self.eat(61):
                kind = T_LESSEQUAL
            else:
                kind = T_LESS
        elif c == 62:  # '>'
            if self.eat(62):
                kind = T_RIGHTSHIFTEQUAL if self.eat(61) else T_RIGHTSHIFT
            elif self.eat(61):
                kind = T_GREATEREQUAL
            else:
                kind = T_GREATER
        elif c == 44:
            kind = T_COMMA
        elif c == 46:  # '.'
            f = self.first()
            if 48 <= f <= 57:
                kind = self.lex_decimal_number(46)
            elif self.eat2(46, 46):
                kind = T_ELLIPSIS
            else:
                kind = T_DOT
        elif c == 10 or c == 13:
            if c == 13:
                self.eat(10)
            if self.nesting == 0 and self.state != S_AFTER_NEWLINE and self.state != S_NON_EMPTY_LOGICAL_LINE:
                self.state = S_AFTER_NEWLINE
                return T_NEWLINE
            if len(self.fstrings) > 0:
                self.fstrings[-1].try_end_format_spec(self.nesting)
            return T_NONLOGICALNEWLINE
        else:
            self.state = S_OTHER
            return self.error_here("Got unexpected token " + chr(c))
        self.state = S_OTHER
        return kind

    def lex_identifier(self, first: int) -> int:
        src = self.src
        n = self.n
        quote = 0
        prefix = 0
        if first == 102 or first == 70:
            prefix = F_FSTRING
        elif first == 116 or first == 84:
            prefix = F_TSTRING
        elif first == 117 or first == 85:
            prefix = F_UNICODE
        elif first == 98 or first == 66:
            prefix = F_BYTE
        elif first == 114:
            prefix = F_RAW_LOWER
        elif first == 82:
            prefix = F_RAW_UPPER
        if prefix != 0:
            f = self.first()
            if f == 39 or f == 34:
                self.flags |= prefix
                self.pos += 1
                quote = f
            else:
                s = self.second()
                if s == 39 or s == 34:
                    if self.try_double_char_prefix(first, f):
                        self.pos += 2
                        quote = s
        if quote != 0:
            if self.flags & (F_FSTRING | F_TSTRING):
                kind = self.lex_fstring_start(quote)
                if kind >= 0:
                    return kind
            return self.lex_string(quote)
        is_ascii = first < 0x80
        pos = self.pos  # (a local for the loop: the field is stored once after it)
        while pos < n:
            c = src[pos]
            if c < 0x80:
                if IDENT[c]:
                    pos += 1
                    continue
                break
            cp = decode_char(src, pos)
            if is_xid_continue(cp):
                is_ascii = False
                pos += char_width(c)
                continue
            break
        self.pos = pos
        if not is_ascii:
            self.flags |= F_NON_ASCII_NAME
            return T_NAME
        tok = self.tok
        # a keyword has at most 8 characters and starts with one of KEYWORD_FIRST's: other
        # names need no slice of the text to look up
        if pos - tok > 8 or not KEYWORD_FIRST[src[tok]]:
            return T_NAME
        return KEYWORDS.get(src[tok:pos], T_NAME)

    def try_double_char_prefix(self, a: int, b: int) -> bool:
        # (a is the first prefix character, b the second)
        lo_a = a | 32
        lo_b = b | 32
        if (a == 114 and lo_b == 102) or (lo_a == 102 and b == 114):
            self.flags |= F_FSTRING | F_RAW_LOWER
        elif (a == 82 and lo_b == 102) or (lo_a == 102 and b == 82):
            self.flags |= F_FSTRING | F_RAW_UPPER
        elif (a == 114 and lo_b == 116) or (lo_a == 116 and b == 114):
            self.flags |= F_TSTRING | F_RAW_LOWER
        elif (a == 82 and lo_b == 116) or (lo_a == 116 and b == 82):
            self.flags |= F_TSTRING | F_RAW_UPPER
        elif (a == 114 and lo_b == 98) or (lo_a == 98 and b == 114):
            self.flags |= F_BYTE | F_RAW_LOWER
        elif (a == 82 and lo_b == 98) or (lo_a == 98 and b == 82):
            self.flags |= F_BYTE | F_RAW_UPPER
        else:
            return False
        return True

    # -- f-strings and t-strings
    def lex_fstring_start(self, quote: int) -> int:
        if quote == 34:
            self.flags |= F_DOUBLE_QUOTES
        if self.eat2(quote, quote):
            self.flags |= F_TRIPLE_QUOTED
        if self.flags & (F_FSTRING | F_TSTRING) == 0:
            return -1
        self.fstrings.append(FStringContext(self.flags, self.nesting, 0))
        return T_FSTRINGSTART if self.flags & F_FSTRING else T_TSTRINGSTART

    def lex_fstring_middle_or_end(self) -> int:
        fs = self.fstrings[-1]
        is_f = fs.flags & F_FSTRING != 0
        q = fs.quote()
        triple = fs.is_triple()
        if triple:
            if self.eat3(q, q, q):
                self.flags = fs.flags
                return T_FSTRINGEND if is_f else T_TSTRINGEND
        elif self.eat(q):
            self.flags = fs.flags
            return T_FSTRINGEND if is_f else T_TSTRINGEND
        in_spec = fs.in_format_spec(self.nesting)
        in_named_unicode = False
        raw = fs.flags & F_RAW != 0
        src = self.src
        n = self.n
        prefix = "f-string: " if is_f else "t-string: "
        while True:
            if self.pos >= n:
                msg = "unterminated triple-quoted string" if triple else "unterminated string"
                self.nesting = fs.nesting
                self.fstrings.pop()
                self.flags |= F_UNCLOSED
                self.error_here(prefix + msg)
                break
            c = src[self.pos]
            if (c == 10 or c == 13) and not triple:
                msg = "newlines are not allowed in format specifiers when using single quotes" if in_spec else "unterminated string"
                self.nesting = fs.nesting
                self.fstrings.pop()
                self.flags |= F_UNCLOSED
                self.error_here(prefix + msg)
                break
            if c == 92:
                self.pos += 1
                f = self.first()
                if f == 123 or f == 125:
                    continue
                elif not raw:
                    if self.eat2(78, 123):
                        in_named_unicode = True
                        continue
                if self.eat(13):
                    self.eat(10)
                else:
                    self.bump()
            elif c == q:
                if triple:
                    if self.pos + 2 < n and src[self.pos + 1] == q and src[self.pos + 2] == q:
                        break
                    self.pos += 1
                else:
                    break
            elif c == 123:
                if self.second() == 123 and not in_spec:
                    self.pos += 2
                else:
                    break
            elif c == 125:
                if in_named_unicode:
                    in_named_unicode = False
                    self.pos += 1
                elif self.second() == 125 and not in_spec:
                    self.pos += 2
                else:
                    break
            else:
                self.pos += 1
        if self.pos == self.tok:
            return -1
        self.flags = fs.flags
        return T_FSTRINGMIDDLE if is_f else T_TSTRINGMIDDLE

    # -- strings
    def lex_string(self, quote: int) -> int:
        if quote == 34:
            self.flags |= F_DOUBLE_QUOTES
        src = self.src
        n = self.n
        if self.eat2(quote, quote):
            self.flags |= F_TRIPLE_QUOTED
        if self.flags & F_TRIPLE_QUOTED:
            qb = b'"' if quote == 34 else b"'"
            while True:
                index = src.find(qb, self.pos)
                if index < 0:
                    self.pos = n
                    self.flags |= F_UNCLOSED
                    self.error_here(MSG_UNCLOSED_STRING)
                    break
                k = index
                while k > self.pos and src[k - 1] == 92:
                    k -= 1
                self.pos = index + 1
                if (index - k) % 2 == 1:
                    continue
                if self.eat2(quote, quote):
                    break
        else:
            while True:
                index = self.pos
                while index < n:
                    c = src[index]
                    if c == quote or c == 10 or c == 13:
                        break
                    index += 1
                if index >= n:
                    self.pos = n
                    self.flags |= F_UNCLOSED
                    self.error_here(MSG_UNCLOSED_STRING)
                    break
                k = index
                while k > self.pos and src[k - 1] == 92:
                    k -= 1
                self.pos = index
                c = src[index]
                if (index - k) % 2 == 1:
                    self.pos += 1
                    if c == 13:
                        self.eat(10)
                    continue
                if c == 13 or c == 10:
                    self.flags |= F_UNCLOSED
                    self.error_here(MSG_UNCLOSED_STRING)
                    break
                self.pos += 1
                break
        return T_STRING

    # -- numbers
    def lex_number(self, first: int) -> int:
        if first == 48:
            f = self.first()
            if f == 120 or f == 88:
                self.pos += 1
                return self.lex_number_radix(16)
            if f == 111 or f == 79:
                self.pos += 1
                return self.lex_number_radix(8)
            if f == 98 or f == 66:
                self.pos += 1
                return self.lex_number_radix(2)
        return self.lex_decimal_number(first)

    def lex_number_radix(self, radix: int) -> int:
        has_digit, _ = self.radix_run(radix)
        if not has_digit:
            return self.error_here("ParseIntError { kind: Empty }")
        return T_INT

    def lex_decimal_number(self, first: int) -> int:
        start_is_zero = first == 48
        has_nonzero = first != 46 and first != 48
        if first != 46:
            _, nz = self.radix_run(10)
            has_nonzero = has_nonzero or nz
        is_float = False
        if first == 46 or self.eat(46):
            if self.eat(95):
                return self.push_error("Invalid Syntax", self.pos - 1, self.pos)
            self.radix_run(10)
            is_float = True
        src = self.src
        p = self.pos
        n = self.n
        if p < n and (src[p] == 101 or src[p] == 69):
            ok = False
            if p + 1 < n and 48 <= src[p + 1] <= 57:
                ok = True
            elif p + 2 < n and (src[p + 1] == 45 or src[p + 1] == 43) and 48 <= src[p + 2] <= 57:
                ok = True
            if ok:
                self.pos += 1
                f = self.first()
                if f == 43 or f == 45:
                    self.pos += 1
                self.radix_run(10)
                is_float = True
        f = self.first()
        if f == 106 or f == 74:
            self.pos += 1
            return T_COMPLEX
        if is_float:
            return T_FLOAT
        if start_is_zero and has_nonzero:
            return self.error_here("Invalid decimal integer literal")
        return T_INT

    def radix_run(self, radix: int) -> tuple[bool, bool]:
        has_digit = False
        has_nonzero = False
        src = self.src
        n = self.n
        while self.pos < n:
            c = src[self.pos]
            if is_digit(c, radix):
                has_digit = True
                if c != 48:
                    has_nonzero = True
                self.pos += 1
            elif c == 95 and self.pos + 1 < n and is_digit(src[self.pos + 1], radix):
                self.pos += 1
            else:
                break
        return has_digit, has_nonzero

    def lex_comment(self) -> int:
        src = self.src
        n = self.n
        p = self.pos
        while p < n:
            c = src[p]
            if c == 10 or c == 13:
                break
            p += 1
        self.pos = p
        return T_COMMENT

    def consume_end(self) -> int:
        while len(self.fstrings) > 0:
            fs = self.fstrings.pop()
            self.nesting = fs.nesting
            prefix = "f-string: " if fs.flags & F_FSTRING else "t-string: "
            self.error_here(prefix + "unterminated string")
        init_nesting = 1 if self.mode == MODE_PARENTHESIZED_EXPRESSION else 0
        if self.nesting > init_nesting:
            self.nesting = 0
            return self.error_here(MSG_EOF)
        if self.state != S_AFTER_NEWLINE and self.state != S_NON_EMPTY_LOGICAL_LINE:
            self.state = S_AFTER_NEWLINE
            return T_NEWLINE
        if len(self.cols) > 0:
            self.cols.pop()
            self.chars.pop()
            return T_DEDENT
        return T_ENDOFFILE

    # -- re-lexing in error recovery
    def re_lex_logical_token(self, nl_start: int) -> bool:
        # (nl_start: the start of the non-logical newline to re-lex, -1 for none)
        if self.nesting == 0:
            return False
        self.nesting -= 1
        if self.flags & F_TRIPLE_QUOTED and self.flags & (F_FSTRING | F_TSTRING):
            return False
        if nl_start < 0:
            return False
        if self.kind == T_RPAR or self.kind == T_RSQB or self.kind == T_RBRACE:
            self.nesting += 1
        self.pos = nl_start
        self.state = S_OTHER
        self.next_token()
        return True

    def re_lex_string_in_interpolation(self, end_kind: int) -> None:
        if len(self.fstrings) == 0:
            return
        fs = self.fstrings[-1]
        if self.kind != T_STRING or self.flags & F_UNCLOSED == 0:
            return
        # only a string without a prefix, of the same quotes
        if self.flags & (F_UNICODE | F_BYTE | F_FSTRING | F_TSTRING | F_RAW) != 0:
            return
        if (self.flags & F_DOUBLE_QUOTES != 0) != (fs.flags & F_DOUBLE_QUOTES != 0):
            return
        if (self.flags & F_TRIPLE_QUOTED != 0) != fs.is_triple():
            return
        quote_len = 3 if self.flags & F_TRIPLE_QUOTED else 1
        p = self.start + quote_len
        src = self.src
        while p < self.n:
            c = src[p]
            if c == 10 or c == 13 or c == 35:
                break
            if c != 32 and c != 9 and c != 12:
                return
            p += char_width(c)
        k = len(self.err_msg)
        if k > 0 and self.err_start[k - 1] == self.start and self.err_end[k - 1] == self.end and self.err_msg[k - 1] == MSG_UNCLOSED_STRING:
            self.err_start.pop()
            self.err_end.pop()
            self.err_msg.pop()
        self.end = self.start + quote_len
        self.kind = end_kind
        self.flags = 0
        self.nesting = fs.nesting
        self.fstrings.pop()
        self.pos = self.end

    def re_lex_raw_string_in_format_spec(self) -> None:
        if self.kind == T_STRING and self.flags & F_UNCLOSED and self.flags & (F_RAW_LOWER | F_BYTE | F_FSTRING | F_TSTRING | F_UNICODE | F_RAW_UPPER) == F_RAW_LOWER:
            k = len(self.err_msg)
            if k > 0 and self.err_start[k - 1] == self.start and self.err_end[k - 1] == self.end and self.err_msg[k - 1] == MSG_UNCLOSED_STRING:
                self.err_start.pop()
                self.err_end.pop()
                self.err_msg.pop()
            self.end = self.start + 1
            self.kind = T_NAME
            self.flags = 0
            self.pos = self.end

    # -- checkpoints
    def checkpoint(self) -> LexerCheckpoint:
        fss: list[FStringContext] = []
        for fs in self.fstrings:
            fss.append(fs.copy())
        return LexerCheckpoint(self.kind, self.start, self.end, self.flags, self.pos, self.state,
                               self.nesting, self.cols[:], self.chars[:], self.has_pending,
                               self.pending_col, self.pending_char, fss, len(self.err_msg))

    def rewind(self, cp: LexerCheckpoint) -> None:
        self.kind = cp.kind
        self.start = cp.start
        self.end = cp.end
        self.flags = cp.flags
        self.pos = cp.pos
        self.state = cp.state
        self.nesting = cp.nesting
        self.cols = cp.cols[:]
        self.chars = cp.chars[:]
        self.has_pending = cp.has_pending
        self.pending_col = cp.pending_col
        self.pending_char = cp.pending_char
        fss: list[FStringContext] = []
        for fs in cp.fstrings:
            fss.append(fs.copy())
        self.fstrings = fss
        k = cp.nerrors
        while len(self.err_msg) > k:
            self.err_start.pop()
            self.err_end.pop()
            self.err_msg.pop()


def is_digit(c: int, radix: int) -> bool:
    if radix == 10:
        return 48 <= c <= 57
    if radix == 16:
        return 48 <= c <= 57 or 97 <= c <= 102 or 65 <= c <= 70
    if radix == 8:
        return 48 <= c <= 55
    return c == 48 or c == 49


def opener_len(flags: int) -> int:
    # the length of a string token's prefix and opening quotes
    q = 3 if flags & F_TRIPLE_QUOTED else 1
    if flags & (F_FSTRING | F_TSTRING | F_BYTE):
        return q + (2 if flags & F_RAW else 1)
    if flags & (F_RAW | F_UNICODE):
        return q + 1
    return q


def closer_len(flags: int) -> int:
    if flags & F_UNCLOSED:
        return 0
    return 3 if flags & F_TRIPLE_QUOTED else 1
