"""Token kinds and flags of the lexer: the order of ruff_python_ast's TokenKind (see THIRD_PARTY_NOTICES)."""
T_NAME = 0
T_INT = 1
T_FLOAT = 2
T_COMPLEX = 3
T_STRING = 4
T_FSTRINGSTART = 5
T_FSTRINGMIDDLE = 6
T_FSTRINGEND = 7
T_TSTRINGSTART = 8
T_TSTRINGMIDDLE = 9
T_TSTRINGEND = 10
T_IPYESCAPECOMMAND = 11
T_COMMENT = 12
T_NEWLINE = 13
T_NONLOGICALNEWLINE = 14
T_INDENT = 15
T_DEDENT = 16
T_ENDOFFILE = 17
T_QUESTION = 18
T_EXCLAMATION = 19
T_LPAR = 20
T_RPAR = 21
T_LSQB = 22
T_RSQB = 23
T_COLON = 24
T_COMMA = 25
T_SEMI = 26
T_PLUS = 27
T_MINUS = 28
T_STAR = 29
T_SLASH = 30
T_VBAR = 31
T_AMPER = 32
T_LESS = 33
T_GREATER = 34
T_EQUAL = 35
T_DOT = 36
T_PERCENT = 37
T_LBRACE = 38
T_RBRACE = 39
T_EQEQUAL = 40
T_NOTEQUAL = 41
T_LESSEQUAL = 42
T_GREATEREQUAL = 43
T_TILDE = 44
T_CIRCUMFLEX = 45
T_LEFTSHIFT = 46
T_RIGHTSHIFT = 47
T_DOUBLESTAR = 48
T_DOUBLESTAREQUAL = 49
T_PLUSEQUAL = 50
T_MINUSEQUAL = 51
T_STAREQUAL = 52
T_SLASHEQUAL = 53
T_PERCENTEQUAL = 54
T_AMPEREQUAL = 55
T_VBAREQUAL = 56
T_CIRCUMFLEXEQUAL = 57
T_LEFTSHIFTEQUAL = 58
T_RIGHTSHIFTEQUAL = 59
T_DOUBLESLASH = 60
T_DOUBLESLASHEQUAL = 61
T_COLONEQUAL = 62
T_AT = 63
T_ATEQUAL = 64
T_RARROW = 65
T_ELLIPSIS = 66
T_AND = 67
T_AS = 68
T_ASSERT = 69
T_ASYNC = 70
T_AWAIT = 71
T_BREAK = 72
T_CLASS = 73
T_CONTINUE = 74
T_DEF = 75
T_DEL = 76
T_ELIF = 77
T_ELSE = 78
T_EXCEPT = 79
T_FALSE = 80
T_FINALLY = 81
T_FOR = 82
T_FROM = 83
T_GLOBAL = 84
T_IF = 85
T_IMPORT = 86
T_IN = 87
T_IS = 88
T_LAMBDA = 89
T_NONE = 90
T_NONLOCAL = 91
T_NOT = 92
T_OR = 93
T_PASS = 94
T_RAISE = 95
T_RETURN = 96
T_TRUE = 97
T_TRY = 98
T_WHILE = 99
T_WITH = 100
T_YIELD = 101
T_CASE = 102
T_LAZY = 103
T_MATCH = 104
T_TYPE = 105
T_UNKNOWN = 106
N_KINDS = 107

# TokenKind's Display, for error messages
KIND_TEXT: list[str] = [
    'name',
    'int',
    'float',
    'complex',
    'string',
    'FStringStart',
    'FStringMiddle',
    'FStringEnd',
    'TStringStart',
    'TStringMiddle',
    'TStringEnd',
    'IPython escape command',
    'comment',
    'newline',
    'NonLogicalNewline',
    'indent',
    'dedent',
    'end of file',
    '`?`',
    '`!`',
    '`(`',
    '`)`',
    '`[`',
    '`]`',
    '`:`',
    '`,`',
    '`;`',
    '`+`',
    '`-`',
    '`*`',
    '`/`',
    '`|`',
    '`&`',
    '`<`',
    '`>`',
    '`=`',
    '`.`',
    '`%`',
    '`{`',
    '`}`',
    '`==`',
    '`!=`',
    '`<=`',
    '`>=`',
    '`~`',
    '`^`',
    '`<<`',
    '`>>`',
    '`**`',
    '`**=`',
    '`+=`',
    '`-=`',
    '`*=`',
    '`/=`',
    '`%=`',
    '`&=`',
    '`|=`',
    '`^=`',
    '`<<=`',
    '`>>=`',
    '`//`',
    '`//=`',
    '`:=`',
    '`@`',
    '`@=`',
    '`->`',
    '`...`',
    '`and`',
    '`as`',
    '`assert`',
    '`async`',
    '`await`',
    '`break`',
    '`class`',
    '`continue`',
    '`def`',
    '`del`',
    '`elif`',
    '`else`',
    '`except`',
    '`False`',
    '`finally`',
    '`for`',
    '`from`',
    '`global`',
    '`if`',
    '`import`',
    '`in`',
    '`is`',
    '`lambda`',
    '`None`',
    '`nonlocal`',
    '`not`',
    '`or`',
    '`pass`',
    '`raise`',
    '`return`',
    '`True`',
    '`try`',
    '`while`',
    '`with`',
    '`yield`',
    '`case`',
    '`lazy`',
    '`match`',
    '`type`',
    'Unknown',
]
