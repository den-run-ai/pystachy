# POSIX integer-descriptor subset. Error cases follow CPython test_select's
# test_error_conditions/test_errno intent; these are focused differential cases,
# not an execution of the unmodified upstream unittest suite.
import select
import time
from select import select as wait

print(wait([], [], [], 0))
print(wait([], [], [], 0.0))
print(wait([], [], [], False))
readable, writable, exceptional = wait([], [], [], 0)
readable.append(7)
writable.append(8)
print(readable, writable, exceptional)
start = time.monotonic()
print(wait([], [], [], 0.01))
print(time.monotonic() - start >= 0.009)
for timeout in [-1.0, float("nan"), float("inf"), float("-inf"), 1e20]:
    try:
        wait([], [], [], timeout)
    except (ValueError, OverflowError) as error:
        print(type(error).__name__, str(error))
for fds in [[-1], [2**31], [-2**32], [1024], [2**20], [0] * 1025]:
    try:
        wait(fds, [], [], 0)
    except (ValueError, OverflowError) as error:
        print(type(error).__name__, str(error))
# Convert the first excess descriptor before raising the count error; neither
# an earlier bad item nor an invalid first excess item is hidden by the count.
for oversized in [[-1] * 1025, [2**31] + [0] * 1024, [0] * 1024 + [-1], [0] * 1024 + [1024], [0] * 1025 + [-1]]:
    try:
        wait(oversized, [], [], 0)
    except (ValueError, OverflowError) as error:
        print(type(error).__name__, str(error))
# Every input position is checked before FD_SET; invalid arguments do not mutate
# the other lists, and timeout validation precedes descriptor validation.
for position in range(3):
    fd_sets: list[list[int]] = [[], [], []]
    fd_sets[position] = [-1]
    try:
        select.select(fd_sets[0], fd_sets[1], fd_sets[2], 0)
    except ValueError as error:
        print(str(error), fd_sets[position])
try:
    select.select([-1], [], [], -1)
except ValueError as error:
    print(str(error))
# The supported runtime values follow CPython's validation order: timeout,
# then read descriptors, write descriptors and exceptional descriptors.
for timeout in [-1.0, float("nan"), float("inf")]:
    try:
        select.select([-1], [-2], [-3], timeout)
    except (ValueError, OverflowError) as error:
        print(str(error))
try:
    select.select([-1], [-2], [-3], 0)
except ValueError as error:
    print(str(error))
try:
    select.select([], [-2], [-3], 0)
except ValueError as error:
    print(str(error))
