import threading, gc, time
n = [0]
stop = [False]
def _run(collect):
    while not stop[0]:
        if collect:
            gc.collect()
        n[0] += 1
        time.sleep(0)
def start(collect):
    threading.Thread(target=_run, args=(bool(collect),), daemon=True).start()
    time.sleep(0.05)
def count():
    return n[0]
def halt():
    stop[0] = True
