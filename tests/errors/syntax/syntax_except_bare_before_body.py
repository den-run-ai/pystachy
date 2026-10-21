# error: syntax_except_bare_before_body.py:6: error: default 'except:' must be last
# (CPython checks the handler before it compiles its body)
def f(x):
    try:
        pass
    except:
        break
    except ValueError:
        pass


print("ran")
