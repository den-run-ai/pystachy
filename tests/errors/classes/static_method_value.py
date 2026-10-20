# error: static_method_value.py:9: error: a static method as a value (Tools.make) is not supported: call it
class Tools:
    @staticmethod
    def make() -> int:
        return 1


t = Tools()
f = t.make
print(f())
