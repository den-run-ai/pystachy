"""Imported by tests/defmods/evaluate while its code runs: it assigns a global of that module
first, and subclasses its Base, bound by then."""
import defmods.evaluate as ev

ev.LIMIT = 7


class Sub(ev.Base):
    def get(self, k):
        return k
