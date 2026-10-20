# error: syntax_parser_before_tokenizer.py:4: error: cannot delete function call
# (CPython's parser reaches the error before its tokenizer reaches the bad indentation)
def f(x):
    del g(x)

  y = 1
