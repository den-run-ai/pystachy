# error: __ipow__ must take self as a positional argument
class V:
    def __ipow__(*args):
        return args[0]


value = V()
value **= 2
