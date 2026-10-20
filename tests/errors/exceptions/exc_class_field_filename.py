# error: a field 'filename' of exception class FE is not supported: it would be OSError's own attribute filename, which decides its str()
class Base(OSError):
    pass


class FE(Base):
    filename: str = ""


print(str(FE("x")))
