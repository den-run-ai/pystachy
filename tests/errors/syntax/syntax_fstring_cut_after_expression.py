# error: syntax_fstring_cut_after_expression.py:5: error: unterminated f-string literal (detected at line 5)
# after an expression, CPython's parser reads the f-string that follows (its rule for a missing
# comma does), to the tokenizer's error that cut it short
x = 1
y = x f"abc {x}
