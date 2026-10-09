# An empty container that a package takes from its own submodule (the package's import runs
# no code of its own module), and one taken through two from-imports, are typed by their first
# use anywhere: an append here, a store in a function of the module that made it.
from infer.rx import ITEMS
from infer.rx_mid import REG
import infer.rx.core

ITEMS.append(1.5)
infer.rx.core.register("a", 1)
print(ITEMS, REG, infer.rx.ITEMS)
