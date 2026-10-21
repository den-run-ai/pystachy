# xa imports ya, whose alias A = <package>.xa.C reads xa through its package while xa's code is
# still running (tests/errors/imports/import_attr_class_alias_subcycle.py)
class C:
    def __init__(self) -> None:
        self.n = 1


import emods.attrcyc.ya
