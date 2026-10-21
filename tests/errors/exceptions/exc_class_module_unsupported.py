# error: class emods.badexc.Oops is not supported: parameter 'x' of method __init__() has no type annotation
from emods.badexc import Oops

try:
    print(1)
except Oops:
    print(2)
