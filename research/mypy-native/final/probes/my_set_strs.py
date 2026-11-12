from typing import Final
class G:
    IGNORED_DUNDERS: Final = {
        "__all__",
        "__author__",
    }
    TYPING_MODULE_NAMES: Final = ("typing", "typing_extensions")
    EXTRA_EXPORTED: Final = {
        "pyasn1_modules.rfc2437.univ",
    }
    def f(self, n: str) -> bool:
        return n in self.IGNORED_DUNDERS or n in self.TYPING_MODULE_NAMES or n in self.EXTRA_EXPORTED
print(G().f("__all__"), G().f("typing"), G().f("zz"), sorted(G.IGNORED_DUNDERS), G.TYPING_MODULE_NAMES)
