# error: assigning 'eload.sub.util' is not supported: the program's first import of the submodule 'eload.sub.util' binds it too
import eload.sub.util
import eload.sub

eload.sub.util = "changed"
