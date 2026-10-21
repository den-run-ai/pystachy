# error: 'Sink' object has no method 'write'
# lib/csv's writer of an object without write() (lib/README.md): CPython raises TypeError when the
# writer is made
import csv


class Sink:
    def __init__(self) -> None:
        self.n = 0


csv.writer(Sink()).writerow(["a", "b"])
