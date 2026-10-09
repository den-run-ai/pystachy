# error: 'os' is bound by two imports, to different modules, functions or classes (not supported)
import os
from eload.reexp import *

if os.name == "nt":
    print("nt: the star import rebound os")
