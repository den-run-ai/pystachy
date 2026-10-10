import sys, io
import av
print("argv", av.nargs())
b = io.StringIO(); old = sys.stdout; sys.stdout = b; b.close()
try:
    av.say("x")
    r = "returned"
except BaseException as e:
    r = "raised " + type(e).__name__
sys.stdout = old
print(r)
