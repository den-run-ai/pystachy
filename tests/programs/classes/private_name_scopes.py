# The lexical class reaches parameters, nested defs/lambdas/comprehensions, global and
# nonlocal declarations, exception bindings and f-string expressions. Call labels stay literal.
__global = 1000
_Locals__global = 10


def raw_keyword(__argument: int) -> int:
    return __argument


class Locals:
    def run(self, __value: int) -> None:
        global __global

        def __bump(__delta: int) -> int:
            nonlocal __value
            __value += __delta
            return __value

        print(__bump(_Locals__delta=2))
        print(__bump.__name__, __bump.__qualname__)
        print(raw_keyword(__argument=__value))
        print((lambda __x: __x + 1)(__value))
        print([__x * 2 for __x in range(3)])
        print(f"{__value=}")
        print((__assigned := 7), __assigned)
        __last = -1
        print([(__last := __x) for __x in range(3)], __last)
        import math as __math
        from math import floor as __floor
        print(__floor(__math.sqrt(10.0)))
        try:
            raise ValueError("private exception")
        except ValueError as __error:
            print(str(__error))
        __global += __value


Locals().run(_Locals__value=4)
print(__global, _Locals__global)
