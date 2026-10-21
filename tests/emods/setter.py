def setup(v):
    global late
    late = v


def ready() -> None:
    global done
    done = True
