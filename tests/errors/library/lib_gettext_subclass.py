# error: inheritance with generic class templates is not supported
# a subclass of NullTranslations, here a translation to add as a fallback: __init__'s fp, a catalog
# file, has no concrete type, so NullTranslations is a template class, which a class cannot derive
# from (lib/compatibility.md#gettext)
from gettext import NullTranslations


class Upper(NullTranslations):
    def gettext(self, message) -> str:
        return message.upper()


t = NullTranslations()
t.add_fallback(Upper())
print(t.gettext("hello"))
