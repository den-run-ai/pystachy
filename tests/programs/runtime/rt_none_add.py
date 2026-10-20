from typing import Optional


class V:
    def __add__(self, o: "V") -> "V":
        return V()


a: Optional[V] = None
b: Optional[V] = None
print(a + b)
