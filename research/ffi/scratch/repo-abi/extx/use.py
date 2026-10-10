import os, signal, sys, time
def nested(d):
    if d:
        return nested(d - 1)
    import pmodx
    return pmodx
m = nested(50)
m.flush()
print("make_total:", m.make_total(20000), "expect 266670")
caps = [m.keep(777 + k) for k in range(3)]
for k in range(3):
    m.make_total(5000)                      # collections run
print("pinned totals:", [m.total_of(c) for c in caps])
del caps
try:
    m.boom(2)
except RuntimeError as e:
    print("caught in Python:", e)
try:
    os.kill(os.getpid(), signal.SIGINT); time.sleep(0.2)
except KeyboardInterrupt:
    print("KeyboardInterrupt reached Python")
print("done")
