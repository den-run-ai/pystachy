# a singleton (class C: ... then C = C()) whose class Pystachy cannot compile, for class_singleton_mod
class Sentinel:
    print("making the class")
Sentinel = Sentinel()
