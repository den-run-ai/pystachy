# error: emods/binds_name.py:1: error: module 'emods.binds_name' binds __name__, which is not supported in an imported module
# (CPython: v is 12, as the module's __name__ is "__main__" by then)
import emods.binds_name

print(emods.binds_name.v)
