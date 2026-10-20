# atexit's callbacks where sys.exit(5) ends the program: they run and the status stays 5; one
# registered while they run does not run, one that clears the list stops the others; the
# program's own _run_exitfuncs(), which empties the list, and _clear()
import atexit
import sys


def never() -> None:
    print("never: cleared before it ran")


def clearer() -> None:
    print("clearer")
    atexit._clear()


def late() -> None:
    print("late: registered during exit, not run")


def registers() -> None:
    print("registers")
    atexit.register(late)


atexit.register(print, "run by _run_exitfuncs")
atexit._run_exitfuncs()
print(atexit._ncallbacks())
atexit.register(print, "cleared")
atexit._clear()
atexit.register(never)
atexit.register(clearer)
atexit.register(registers)
print("exiting")
sys.exit(5)
