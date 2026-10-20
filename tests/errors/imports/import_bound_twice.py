# error: 'os' is bound by two imports, to different modules, functions or classes (not supported)
import os

print(os.name)
import eload.fakeos as os

print(os.name)
