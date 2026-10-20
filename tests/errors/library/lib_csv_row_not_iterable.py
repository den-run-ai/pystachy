# error: 'Point' object is not iterable
# lib/csv's writerow() of an object that is no iterable (lib/README.md): CPython raises csv.Error
import csv
import sys


class Point:
    def __init__(self, x: int) -> None:
        self.x = x


csv.writer(sys.stdout).writerow(Point(1))
