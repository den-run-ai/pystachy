# error: syntax_fstring_error_after.py:4: error: f-string: expecting '=', or '!', or ':', or '}'
# a tokenizer error in a field that CPython's parser does not get to replaces no parser error
x = 1
print(f"{x $ 1_a}")
