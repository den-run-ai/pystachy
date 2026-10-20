# error: syntax_fstring_expression_brackets.py:4: error: f-string: expecting a valid expression after '{'
# no expression is complete in a field that fails inside its brackets
x = 1
print(f"{(x $)}")
