# an exception class Pystachy cannot compile: an error only where the program uses it


class Oops(Exception):
    def __init__(self, x):
        self.x = x
