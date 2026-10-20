# Definition time: see tests/defmods/evaluate. Pystachy evaluates the parts of a default value it
# can compile, reads a global that another module assigned first, and "%c" % n formats the
# character n.
print("main: start")
import defmods.evaluate as ev

print(ev.limit(), ev.LIMIT, ev.V)
print("[%3c]" % "é", "[%c]" % 233, "[%-2c]" % "€", "[%c]" % 65)
