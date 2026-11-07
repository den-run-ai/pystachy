# open() descriptors stay available to this process but are closed by child exec.
import os
import tempfile


def quote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def private_to_process(fd: int, path: str) -> bool:
    # The shell may reuse the numeric descriptor. It must not still name our file.
    return os.system("test ! " + quote("/dev/fd/" + str(fd)) + " -ef " + quote(path)) == 0


directory = tempfile.mkdtemp()
path = directory + "/file with spaces"
with open(path, "w") as writer:
    print(writer.write("hello\n"), private_to_process(writer.fileno(), path))
with open(path, "r") as reader:
    print(reader.read().strip(), private_to_process(reader.fileno(), path))
with open(path, "rb") as binary:
    print(binary.read() == b"hello\n", private_to_process(binary.fileno(), path))
os.remove(path)
os.rmdir(directory)
