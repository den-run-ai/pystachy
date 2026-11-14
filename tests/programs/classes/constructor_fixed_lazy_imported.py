from mods.constructor_lazy_base import ImportedBase, QualifiedBase
import mods.constructor_lazy_imported


print(ImportedBase([1]).get(), QualifiedBase((2, 3)).get())
