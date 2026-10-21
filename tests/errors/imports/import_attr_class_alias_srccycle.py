# error: class 'emods.attrcyc.aa.C' cannot be used as a value
# (an alias of a module's own alias of a class stays an error where that module imports the
# alias's module back: aa binds A = C only where that statement runs, after its import of ab, so
# CPython raises AttributeError: partially initialized module 'emods.attrcyc.aa' has no attribute
# 'A', where checking that class C is bound would let ab's B = aa.A run)
import emods.attrcyc.aa

print("main")
