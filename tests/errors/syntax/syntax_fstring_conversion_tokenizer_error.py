# error: syntax_fstring_conversion_tokenizer_error.py:4: error: invalid decimal literal
# after a conversion, CPython's parser reads the next token: a tokenizer error comes first
x = 1
print(f"{x!r 1b}")
