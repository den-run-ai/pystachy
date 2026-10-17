# a Python exception whose str() raises, inside an extension module: the host does not crash
from ffi import export
from pyobj import import_module


@export
def go() -> str:
    try:
        import_module("xbad").attr("boom").call([])
        return "no error"
    except Exception as e:
        return "caught " + str(e)
