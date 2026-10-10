import sys, signal
def nested(d):
    if d:
        return nested(d - 1)
    import pmod            # PyInit_pmod runs here, deep in the stack: pys_init records this frame
    return pmod
m = nested(int(sys.argv[1]))
print("SIGINT handler now:", signal.getsignal(signal.SIGINT))
print("make_total from a shallower frame:", m.make_total(20000), "expect 266670")
sys.stdout.flush()
if len(sys.argv) > 2:
    try:
        m.boom(2)
    except Exception as e:
        print("caught in Python:", repr(e))
    print("still alive")
