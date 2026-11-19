# error: 'Absent' is imported only under if TYPE_CHECKING:, from module 'tcbad.absent', which the program does not import, so an annotation cannot name it
# Nothing is loaded for an if TYPE_CHECKING: import: its class exists only where the program
# imports its module
import tcbad.unloaded

print(tcbad.unloaded.Holder(1).item)
