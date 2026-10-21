# Only None is accepted, not falsy int/string/union results. Explicit calls keep the result.
class Maybe:
    def __init__(self, n: int) -> int | None:
        self.n = n
        if n:
            return 0
        return None


for n in [0, 1]:
    try:
        m = Maybe(n)
        print("made", m.n)
    except TypeError as e:
        print("TypeError", e)
m = Maybe(0)
print("explicit", m.__init__(1), m.n)
method = m.__init__
print("saved", method(3), m.n)


class Several:
    def __init__(self, n: int) -> int | str | None:
        if n == 1:
            return 0
        if n == 2:
            return ""
        return None


for n in [0, 1, 2]:
    try:
        Several(n)
        print("several made", n)
    except TypeError as e:
        print("TypeError", e)
