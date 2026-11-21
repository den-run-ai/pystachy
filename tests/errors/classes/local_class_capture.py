# error: local_class_capture.py:4: error: a class inside a function is not supported: it reads k, a name of the function
# A method that reads the function's variable needs its frame, which the module's class lacks
def run(k: int) -> None:
    class C:
        def get(self) -> int:
            return k

    print(C().get())


run(3)
