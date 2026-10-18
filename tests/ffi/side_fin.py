import atexit, threading, time


def setup(x):
    atexit.register(lambda: print("atexit ran"))

    def late():
        time.sleep(0.2)
        print("thread finished")

    threading.Thread(target=late).start()  # non-daemon: joined at finalization
