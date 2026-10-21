# error: syntax_except_star_mixed.py:7: error: cannot have both 'except' and 'except*' on the same 'try'
def f(x):
    try:
        pass
    except* ValueError:
        pass
    except TypeError:
        pass


print("ran")
