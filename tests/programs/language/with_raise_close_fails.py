# A close failure replaces an uncaught ordinary exception too, without a try statement.
with open("/dev/full", "w") as f:
    f.write("lost")
    raise ValueError("body failed")
