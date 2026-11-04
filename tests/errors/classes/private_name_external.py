# error: 'C' object has no attribute '__value'
# Direct reads of statically missing attributes remain unsupported; a private field is not
# accidentally exposed under its unmangled spelling. getattr()/hasattr() cover dynamic lookup.
class C:
    def __init__(self) -> None:
        self.__value = 1


print(C().__value)
