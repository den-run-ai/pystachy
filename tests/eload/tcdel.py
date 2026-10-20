TYPE_CHECKING = False
import eload.tcdel as me

del me.TYPE_CHECKING
try:
    if TYPE_CHECKING:
        print("checking")
except NameError as e:
    print(e)
