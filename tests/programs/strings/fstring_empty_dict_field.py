# An empty dict display in a replacement field: a format spec that starts with '{{' opens a field
# (PEP 701) whose expression here is '{}', which formats as the text '{}'


class F:
    def __format__(self, spec: str) -> str:
        return "<" + spec + ">"


print(f"{F():{{}}}", f"{F():a{{}}b}", f"{F():{{}}{{}}}|{F():{{}}{1}}")
print(f"{ {} }|{ {}!r}|{ {}!s:>4}|{ {}!a:*^6}|{ {}=}|{ {} = !s}|{ {}:}")


def spec(v: int) -> str:
    return f"{v:{{}}}"


try:
    print(spec(5))
except ValueError as e:
    print("ValueError:", e)
try:
    print(f"{ {}!r:{{}}}")
except ValueError as e:
    print("ValueError:", e)
