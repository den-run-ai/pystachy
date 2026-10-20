# error: module '_io' has no attribute 'open_code'
# (open_code() opens a binary file, which open() does not make: #493)
import _io

_io.open_code("tests/lib_io_cmodule.py")
