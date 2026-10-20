# error: syntax_fstring_spec_quote.py:4: error: unterminated string literal (detected at line 4)
# the f-string's quote in a format spec ends it; the tokenizer's error after it comes first
x = 1
print(f"{x:"}")
