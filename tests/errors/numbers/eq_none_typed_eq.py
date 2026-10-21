# error: eq_none_typed_eq.py:11: error: expected int, got None
class V:
    def __init__(self, v: int) -> None:
        self.v = v

    def __eq__(self, o: int) -> bool:
        return self.v == o


print(V(1) == 1)
print(V(1) == None)  # (CPython calls __eq__ with None, which its int parameter cannot hold)
