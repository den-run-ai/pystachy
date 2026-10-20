# error: cannot infer the type of 'gettext._localedirs'
# gettext's catalog lookups do not compile yet (lib/compatibility.md#gettext): _localedirs has a type
# only where bindtextdomain() fills it, translation() imports locale and keys its cache by a class
import gettext
print(gettext.gettext("hi"))
