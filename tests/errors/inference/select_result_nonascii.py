# error: f() returns both list[str] and str (each function has one return type): its parameter 'mode' chooses which, and this call gives it no literal: pass a literal or annotate the result
# A selector's str literal is ASCII: the compiler holds a str as its UTF-8 bytes, whose count is
# no len() of a str with other characters ("é" has one).
def f(s: str, mode: str = "é"):
    if len(mode) == 1:
        return [s]
    return s


print(f("a"))
