# error: 'int' has no method 'no_such_thing' (compiling emods.tmeth.Acc.broken(int)
from emods.tmeth import Acc

print(Acc(1).broken(2))
