# set_inheritable controls exec inheritance without changing the open file.
import os
import tempfile

root = tempfile.mkdtemp()
path = root + "/input"
with open(path, "w") as stream:
    stream.write("inherited")
with open(path, "r") as stream:
    closed_fd = stream.fileno()
    command = "test /dev/fd/" + str(closed_fd) + " -ef " + path
    for value in [False, True, False]:
        os.set_inheritable(stream.fileno(), value)
        print(os.system(command) == 0)
    for flag in [0, 2, -1, 0]:
        os.set_inheritable(stream.fileno(), flag)
        print(os.system(command) == 0)
    print(stream.read())
    for wide in [-1099511627776, 1099511627776]:
        try:
            os.set_inheritable(stream.fileno(), wide)
        except OverflowError as error:
            print(error)
for fd in [-1, -1099511627776, 1099511627776, closed_fd]:
    try:
        os.set_inheritable(fd, True)
    except (OSError, OverflowError) as error:
        print(error)
os.remove(path)
os.rmdir(root)
