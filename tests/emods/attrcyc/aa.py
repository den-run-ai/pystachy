# aa imports ab, whose alias B = aa.A reads aa's own alias of its class, A = C, while aa's code is
# still running, before that statement (tests/errors/imports/import_attr_class_alias_srccycle.py)
class C:
    def __init__(self) -> None:
        self.n = 1


import emods.attrcyc.ab

A = C
