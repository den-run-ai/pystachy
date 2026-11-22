# a subclass of NullTranslations, here a translation to add as a fallback: __init__'s fp, a catalog
# file, has no concrete type, so NullTranslations is a class template, from which a class without
# an __init__ of its own derives as from each specialization (#962)
from gettext import NullTranslations


class Upper(NullTranslations):
    def gettext(self, message) -> str:
        return message.upper()


t = NullTranslations()
t.add_fallback(Upper())
print(t.gettext("hello"))
