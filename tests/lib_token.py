# token: Pystachy's copy of CPython's Lib/token.py (lib/token.py), whose __all__ and tok_name are
# written out where CPython builds them from globals()
import token
from token import *

print(len(token.__all__), token.__all__)
print(len(tok_name), tok_name)
print(len(EXACT_TOKEN_TYPES), EXACT_TOKEN_TYPES)
print(ENDMARKER, NAME, OP, TYPE_COMMENT, SOFT_KEYWORD, FSTRING_START, COMMENT, NL, ERRORTOKEN)
print(ENCODING, N_TOKENS, NT_OFFSET, token.NT_OFFSET)
print(tok_name[NAME], tok_name[token.OP], tok_name[NT_OFFSET], tok_name[EXACT_TOKEN_TYPES["->"]])
print(ISTERMINAL(NAME), ISTERMINAL(NT_OFFSET), ISNONTERMINAL(NT_OFFSET + 1), ISNONTERMINAL(OP))
print(ISEOF(ENDMARKER), ISEOF(NEWLINE), token.ISEOF(0))
for op in ["(", "**=", "->", ":=", "!", "..."]:
    print(op, EXACT_TOKEN_TYPES[op], tok_name[EXACT_TOKEN_TYPES[op]])
print(sorted(EXACT_TOKEN_TYPES.items())[:4], max(tok_name), min(tok_name))
