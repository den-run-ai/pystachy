# error: 'int' has no method '__index__'
# NullTranslations.ngettext() takes its count through operator.index(), which lib's operator does
# not apply to an int, and warns through warnings, which does not compile (lib/compatibility.md#gettext)
from gettext import NullTranslations
print(NullTranslations().ngettext("file", "files", 2))
