try:
    with open("/dev/fd/3", "rb") as f:
        print("fd3", f.read(4).hex())
except OSError as e:
    print("fd3", type(e).__name__)
