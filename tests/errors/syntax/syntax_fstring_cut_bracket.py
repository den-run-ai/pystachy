# error: syntax_fstring_cut_bracket.py:5: error: f-string: expecting '}'
# the f-string's quote in a field starts a string, which the line ends: the bracket open in the
# field is never closed, but CPython's parser meets the tokenizer's error first
x = [1]
y = f"{x[0"
z = 2
