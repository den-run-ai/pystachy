from importlib import import_module

import_module(".child", __package__)
mod = import_module(".child", __package__)
VALUE = mod.VALUE
