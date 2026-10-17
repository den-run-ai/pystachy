# error: class emods.anyhold.Holder is not supported: emods.anyhold.Holder.__init__() is not supported: parameter 'value': typing.Any is only supported
# An imported module's class whose __init__ takes a parameter annotated Any is an error only where
# the program uses it
from emods.anyhold import Holder, ident

print(ident(1), ident("s"))
print(Holder(1).value)
