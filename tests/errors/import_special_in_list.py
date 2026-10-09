# error: emods/special.py:9: error: unsupported type annotation
# Lists of Pair compare their items with Pair.__eq__, which cannot be compiled (its parameter is
# annotated object): an error, not the identity test the runtime's equality would fall back to.
import emods.special
print([emods.special.Pair(1)] == [emods.special.Pair(1)])
