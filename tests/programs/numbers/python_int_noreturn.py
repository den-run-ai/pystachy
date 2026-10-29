# pystachy: python-int
# A never-returning template's unused value still needs a valid promoting-int IR type.
def fail(message):
    raise ValueError(message)


def parse(text: str) -> int:
    if text.isdigit():
        return int(text)
    return fail("bad " + text)


def choose(ok: bool) -> int:
    return 2 ** 70 if ok else fail("branch")


for text in ["1180591620717411303424", "bad"]:
    try:
        print(parse(text))
    except ValueError as error:
        print(error)
for ok in [True, False]:
    try:
        print(choose(ok))
    except ValueError as error:
        print(error)
