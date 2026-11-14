from mods.constructor_lazy_base import ImportedBase as BaseAlias
import mods.constructor_lazy_base as bases


class ImportedUnused(BaseAlias):
    def get(self) -> int:
        return self.missing


class QualifiedUnused(bases.QualifiedBase):
    def get(self) -> int:
        return self.missing
