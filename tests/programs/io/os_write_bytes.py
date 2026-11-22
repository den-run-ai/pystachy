# os.write sends raw bytes and reports how many the descriptor accepted.
import os
import tempfile

path = os.path.join(tempfile.mkdtemp(), "result")
with open(path, "wb") as output:
    fd = output.fileno()
    print(os.write(fd, b"A\xff\0"), os.write(fd, b""))
with open(path, "rb") as data:
    print(data.read().hex())
for fd in [-1, 1 << 32]:
    try:
        os.write(fd, b"")
    except (OSError, OverflowError) as error:
        print(type(error).__name__, str(error))
os.remove(path)
os.rmdir(os.path.dirname(path))
