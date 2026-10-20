# error: 'int' has no method '__index__'
# NullTranslations.ngettext() takes its count through operator.index(), which lib's operator does
# not apply to an int, and for a count of another type finds the frame to warn from with
# sys._getframe(), which is not supported (lib/compatibility.md#gettext)
from gettext import NullTranslations
print(NullTranslations().ngettext("file", "files", 2))
