# error: syntax_fstring_comma_lookahead.py:6: error: invalid decimal literal
# after a missing comma, CPython's parser reads the next expression as far as it goes: to the
# tokenizer's error here
x = 1
y = 2
print(f"{x y + 1_a}")
