from export_settings import *

print(default, _private, option)
try:
    print(hidden)
except NameError:
    print("hidden")

import export_settings

export_settings.__all__.append("hidden")
from export_settings import *

print(hidden)
