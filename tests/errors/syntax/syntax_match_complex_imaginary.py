# error: syntax_match_complex_imaginary.py:4: error: imaginary number required in complex literal
def f(x):
    match x:
        case 1 + 2:
            return 1


print("ran")
