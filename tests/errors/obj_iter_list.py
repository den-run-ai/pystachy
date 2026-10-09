# error: iter() returned non-iterator of type 'list'
# (CPython calls __iter__, then rejects what it returns)
class Seq:
    def __iter__(self) -> list[int]:
        return [1, 2]


for x in Seq():
    print(x)
