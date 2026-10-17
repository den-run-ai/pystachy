import signal, threading, time


def start():
    def send():
        time.sleep(0.3)
        signal.pthread_kill(threading.get_ident(), signal.SIGINT)  # (to this thread, not the main one)

    threading.Thread(target=send, daemon=True).start()
