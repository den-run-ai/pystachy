# error: 'pi' is bound both as a variable and as a function, class or import
from math import pi
for i in range(2):
    print(pi)
    pi = 3.0
