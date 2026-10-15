# error: user-defined context managers cannot be used in 'with'
class Manager:
    def __enter__(self):
        return self
    def __exit__(self, et, ev, tb):
        return False
with Manager():
    print("ok")
