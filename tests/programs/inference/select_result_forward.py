# A function that passes its own parameter on as another's selector is compiled for each literal
# it is given too, by position or by keyword under another name.
def repair(s: str, logging: bool = False):
    fixed = s.strip()
    if logging:
        return fixed, ["stripped"]
    return fixed


def loads(s: str, logging: bool = False):
    return repair(s, logging)


def loads_kw(s, log=False):
    return repair(s, logging=log)


print(loads(" a "))
value, log = loads(" b ", True)
print(value, log)
print(loads_kw(" c "), loads_kw(" d ", log=True))
