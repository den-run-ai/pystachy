# error: syntax_except_bare_not_last.py:5: error: default 'except:' must be last
def f(x):
    try:
        pass
    except:
        pass
    except ValueError:
        pass


print("ran")
