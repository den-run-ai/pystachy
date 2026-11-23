from conditional_extra import *
import conditional_extra

conditional_extra.__all__.append("b")
from conditional_extra import *

print(b)
conditional_extra.b = 11
from conditional_extra import *

print(b)
conditional_extra.__all__.remove("b")
conditional_extra.b = 12
from conditional_extra import *

print(b)
