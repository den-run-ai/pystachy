import sys

if len(sys.argv) > 5:
    LIMIT = 1


class Box:
    def get(self, n=LIMIT):
        return n
