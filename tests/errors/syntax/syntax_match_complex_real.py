# error: syntax_match_complex_real.py:4: error: real number required in complex literal
def f(x):
    match x:
        case -1j + 2j:
            return 1


print("ran")
