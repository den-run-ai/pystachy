# A module global given only a call's None reads as None in its module and in the importer's
# code. A store from the importer (mods.none_call_global.x = 5) still gives it another value.
import mods.none_call_global

mods.none_call_global.show()
print(mods.none_call_global.x)
mods.none_call_global.x = 5
mods.none_call_global.show()
print(mods.none_call_global.x + 1)
