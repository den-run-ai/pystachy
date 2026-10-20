# error: syntax_fstring_expecting_operand.py:4: error: f-string: expecting '=', or '!', or ':', or '}'
# the longest expression a field starts with is x.y, so CPython's parser expects '=', '!', ':' or '}'
x = 1
print(f"{x.y.$}")
