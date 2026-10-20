# error: syntax_fstring_spec_unclosed.py:5: error: f-string: expecting '}', or format specs
# the f-string ends at its quote, even in a format spec
x = 1
y = 2
z = f"{x:{y}{{"
