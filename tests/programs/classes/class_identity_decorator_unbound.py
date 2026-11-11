# CPython reads a class's decorators before it runs the class body: an identity decorator
# (@final) whose import has not run yet raises NameError there, before the body's default runs.
def mark(s: str) -> str:
    print(s)
    return s


print("start")


@final
class A:
    tag: str = mark("body")


from typing import final

print("never", A.tag)
