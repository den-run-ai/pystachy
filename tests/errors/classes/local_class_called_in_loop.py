# error: local_class_called_in_loop.py:4: error: a class inside a function is not supported: run() is no function that runs at most once
# A call in a loop runs the class statement each time: CPython makes two classes
def run() -> None:
    class C:
        pass

    print(C.__qualname__)


for _ in range(2):
    run()
