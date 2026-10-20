# error: an import of 'm' in a function that declares it global is not supported
import eload.fine as m


def switch() -> None:
    global m
    import eload.fine2 as m


print(m.V)
switch()
print(m.V)
