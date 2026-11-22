# A function without a return annotation whose returns join to no type, where a parameter's literal
# argument decides which returns run, compiles to an instance for each literal: repair() returns a
# str where logging is False (also by default) and a tuple where it is True, by position or keyword;
# load()'s selector is keyword-only.
def repair(s: str, logging: bool = False):
    fixed = s.strip()
    if logging:
        return fixed, ["stripped"]
    return fixed


def load(s: str, *, strict: bool = False):
    if strict:
        return [s]
    return s


print(repair(" a "))
value, log = repair(" b ", logging=True)
print(value, log)
print(repair(" c ", False), repair(" d ", True))
print(repair(" e ").upper(), len(repair(" f ", logging=True)))
print(load("g"), load("h", strict=True), load("i", strict=False))
