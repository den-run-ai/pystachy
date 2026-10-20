# gettext, CPython 3.13.16's adapted in lib/gettext.py: the module imports, and the parts that
# look up no catalog work
import gettext
from gettext import NullTranslations

t = NullTranslations()
print(t.gettext("hello"), t.pgettext("menu", "Open"), t.charset(), t.info())
fallback = NullTranslations()
t.add_fallback(fallback)
print(t.gettext("again"), t.pgettext("ctx", "msg"))
print(gettext.textdomain(), gettext.textdomain("app"), gettext.textdomain())
print(gettext.bindtextdomain("app", "/nonexistent/locale"), gettext.bindtextdomain("app"))
print("NullTranslations" in gettext.__all__, len(gettext.__all__))
