"""The host owns this batch; the compiled consumer retains its buffer export."""
from array import array

data = array("d", [1.0, 2.0, 3.0, 4.0])
weights = array("d", [0.25, 0.5, 0.75, 1.0])

copy_bytes = 0


def copy_data():
    global copy_bytes
    copy_bytes += data.itemsize * len(data)
    return array("d", data)
