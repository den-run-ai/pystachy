# error: syntax_except_star_break.py:7: error: 'break', 'continue' and 'return' cannot appear in an except* block
def f(x):
    for y in x:
        try:
            pass
        except* ValueError:
            break


print("ran")
