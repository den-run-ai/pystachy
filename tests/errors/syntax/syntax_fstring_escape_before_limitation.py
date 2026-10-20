# error: syntax_fstring_escape_before_limitation.py:3: error: (unicode error) 'unicodeescape' codec can't decode bytes in position 0-1: truncated \xXX escape
# an escape error in an f-string's text comes before a Pystachy limitation in a later field
print(f"\x{é}")
