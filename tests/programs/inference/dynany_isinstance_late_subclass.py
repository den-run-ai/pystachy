# isinstance() of an Any value against a class of a module that opts in to dynamic Any, compiled by
# the first log() below, before the program boxes objects of the subclasses it defines after that
# call: their objects pass the test too, as in CPython, where the test once missed every subclass
# that the program boxed later (a filter was then called as a function)
import dynisa_filters

lg = dynisa_filters.Logger()
lg.log("first")


class OnlyEven(dynisa_filters.Filter):
    def filter(self, record: dynisa_filters.Record) -> bool:
        return record.msg.endswith("0") or record.msg.endswith("2")


class Stricter(OnlyEven):
    pass


def not_two(record: dynisa_filters.Record) -> bool:
    return not record.msg.endswith("2")


lg.addFilter(OnlyEven())
for i in range(3):
    lg.log("n%d" % i)
lg.addFilter(Stricter())
lg.addFilter(not_two)
for i in range(3):
    lg.log("m%d" % i)
print([isinstance(f, dynisa_filters.Filter) for f in lg.filters], [isinstance(f, OnlyEven) for f in lg.filters])
