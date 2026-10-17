# C stdio only creates a real OS descriptor; select runs through the public
# Python API under CPython and the native runtime under Pystachy.
from ffi import extern, c_void_p, c_int
from select import select


@extern("")
def tmpfile() -> c_void_p: ...


@extern("")
def fileno(file: c_void_p) -> c_int: ...


@extern("")
def fclose(file: c_void_p) -> c_int: ...


file = tmpfile()
assert file != 0
fd = fileno(file)
other_file = tmpfile()
assert other_file != 0
other_fd = fileno(other_file)
readers = [other_fd, fd, other_fd]
writers = [fd, other_fd, fd]
exceptions = [fd, fd]
for iteration in range(20):
    ready = select(readers, writers, exceptions, 0)
    assert ready == (readers, writers, [])
    # The result lists are fresh and preserve original order and duplicates.
    ready[0].append(-1)
    assert readers == [other_fd, fd, other_fd]
print("read/write readiness, duplicates, order and independent lists")
print(select([fd], [], []) == ([fd], [], []))
print(select([fd], [], [], None) == ([fd], [], []))
print(fclose(file), fclose(other_file))
try:
    select([fd], [], [], 0)
except OSError as error:
    print(type(error).__name__, str(error))
