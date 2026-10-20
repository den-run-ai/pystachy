# error: syntax_fstring_debug_tokenizer_error.py:4: error: invalid decimal literal
# after a field's '=', CPython's parser reads the next token: a tokenizer error comes first
x = 1
print(f"{x=1b}")
