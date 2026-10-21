# from convertdate import * (ports/convertdate) takes the names convertdate's __all__ lists: the
# 16 modules the port has. The port leaves out bahai, french_republican and persian, and while
# __all__ still named them, the import stopped at bahai with an AttributeError. dublin's functions
# are a DayCount's bound methods, bound to module names.
from convertdate import *

jd = gregorian.to_jd(2024, 3, 11)
print(jd, gregorian.from_jd(jd), julian.from_gregorian(2024, 3, 11), hebrew.from_gregorian(2024, 3, 11))
print(islamic.from_gregorian(2024, 3, 11), coptic.from_gregorian(2024, 3, 11),
      indian_civil.from_gregorian(2024, 3, 11), ordinal.from_gregorian(2024, 3, 11))
print(armenian.from_gregorian(2024, 3, 11), positivist.from_gregorian(2024, 3, 11), utils.jwday(jd))
print(holidays.thanksgiving(2024), holidays.easter(2024))
dc = dublin.from_gregorian(2024, 3, 11)
print(dc, dublin.to_gregorian(dc), dublin.to_julian(dc), dublin.from_julian(2024, 2, 27),
      dublin.to_jd(dc), dublin.from_jd(jd), dublin.EPOCH, dublin.to_gregorian(0), dublin.to_gregorian(-0.5))
