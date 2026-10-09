# error: emods/syntax_non_utf8.py:3: error: (unicode error) 'utf-8' codec can't decode byte 0xe9 in position 3: unexpected end of data
# (CPython compiles an imported module from its bytes, so only a string or a name must be UTF-8)
import emods.syntax_non_utf8

print("ran")
