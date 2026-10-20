# The line of an exception that nothing catches writes a surrogate as \udcff, as CPython's stderr does.
class E(Exception):
    pass


try:
    raise E("u" + chr(0xDABC))
except E as e:
    print("caught", repr(e))
raise ValueError("bad " + chr(0xDCFF))
