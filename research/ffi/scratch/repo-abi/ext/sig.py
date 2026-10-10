import os, signal, time, sys
import pmod
try:
    os.kill(os.getpid(), signal.SIGINT)
    time.sleep(0.2)
    print("no KeyboardInterrupt")
except KeyboardInterrupt:
    print("Python got KeyboardInterrupt as usual")
