# A class without an __init__ of its own derives from a class template whose __init__ takes Any:
# Derived(1) is of the specialization of Derived that derives from Holder's for an int (#962)
from typing import Any


class Holder:
    def __init__(self, value: Any) -> None:
        self.value = value


class Derived(Holder):
    pass


print(Derived(1).value)
