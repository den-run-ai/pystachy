# error: iterating over Seq by its __getitem__ is not supported (CPython calls __getitem__(0), __getitem__(1), ... until IndexError): define __iter__
class Seq:
    def __getitem__(self, i: int) -> int:
        return i


print(3 in Seq())
