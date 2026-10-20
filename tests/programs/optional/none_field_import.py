# An imported class whose field always holds None: its objects work.
import mods.nonefield

print(mods.nonefield.count(), mods.nonefield.Hooks().n, mods.nonefield.Hooks().ready)
