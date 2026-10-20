# convertdate's calendar conversions (ports/convertdate): Gregorian dates to Julian days and to
# the Julian, Hebrew, Islamic, Coptic, Indian civil, Armenian, Positivist and Mayan calendars and
# back, over edge cases and a run of consecutive days; month lengths, leap years, month
# calendars, ISO weeks, ordinal dates, the weekday helpers and the error paths.
from convertdate import hebrew

# before anything else of hebrew: year_days, month_days and to_jd call one another (PORT.md)
print("hebrew year days", hebrew.year_days(5784), hebrew.year_days(5785), hebrew.year_days(5786))

from convertdate import armenian, coptic, gregorian, indian_civil, islamic, iso
from convertdate import julian, julianday, mayan, ordinal, positivist, utils

DATES = [(2024, 3, 11), (2000, 1, 1), (1999, 12, 31), (1582, 10, 15), (1582, 10, 4),
         (1900, 2, 28), (1900, 3, 1), (2000, 2, 29), (2024, 2, 29), (2100, 3, 1), (1, 1, 1),
         (0, 12, 31), (-500, 6, 15), (-4713, 11, 24), (9999, 12, 31), (2012, 12, 21),
         (1970, 1, 1), (1789, 1, 1), (622, 7, 19), (284, 8, 29), (-3113, 8, 11)]

for y, m, d in DATES:
    jd = gregorian.to_jd(y, m, d)
    print((y, m, d), "jd", jd, gregorian.from_jd(jd), "weekday", utils.jwday(jd),
          "julian", julian.from_gregorian(y, m, d))
    h = hebrew.from_gregorian(y, m, d)
    i = islamic.from_gregorian(y, m, d)
    c = coptic.from_gregorian(y, m, d)
    n = indian_civil.from_gregorian(y, m, d)
    o = ordinal.from_gregorian(y, m, d)
    print("  hebrew", h, "islamic", i, "coptic", c, "indian", n, "ordinal", o)
    back = [hebrew.to_gregorian(h[0], h[1], h[2]), islamic.to_gregorian(i[0], i[1], i[2]),
            coptic.to_gregorian(c[0], c[1], c[2]), indian_civil.to_gregorian(n[0], n[1], n[2]),
            ordinal.to_gregorian(o[0], o[1])]
    j = julian.from_gregorian(y, m, d)
    back.append(julian.to_gregorian(j[0], j[1], j[2]))
    print("  back", back, all(g == (y, m, d) for g in back))
    if jd > armenian.EPOCH + 365:  # its year 0 is out of range for to_jd
        a = armenian.from_gregorian(y, m, d)
        print("  armenian", a, armenian.to_gregorian(a[0], a[1], a[2]))
    if jd >= positivist.EPOCH:
        p = positivist.from_gregorian(y, m, d)
        print("  positivist", p, positivist.to_gregorian(p[0], p[1], p[2]))
    if jd >= mayan.EPOCH:
        lc = mayan.from_gregorian(y, m, d)
        print("  mayan", lc, mayan.to_haab(jd), mayan.to_tzolkin(jd),
              mayan.to_gregorian(lc[0], lc[1], lc[2], lc[3], lc[4]))

# consecutive days through a Hebrew leap year (Adar I and II), the ends of Islamic, Coptic,
# Indian and Armenian years and a Gregorian leap day; each calendar there and back
start = gregorian.to_jd(2023, 9, 1)
bad = 0
total = 0
for k in range(430):
    jd = start + k
    g = gregorian.from_jd(jd)
    h = hebrew.from_jd(jd)
    i = islamic.from_jd(jd)
    c = coptic.from_jd(jd)
    n = indian_civil.from_jd(jd)
    a = armenian.from_jd(jd)
    p = positivist.from_jd(jd)
    j = julian.from_jd(jd)
    if (gregorian.to_jd(g[0], g[1], g[2]) != jd or hebrew.to_jd(h[0], h[1], h[2]) != jd
            or islamic.to_jd(i[0], i[1], i[2]) != jd or coptic.to_jd(c[0], c[1], c[2]) != jd
            or indian_civil.to_jd(n[0], n[1], n[2]) != jd or armenian.to_jd(a[0], a[1], a[2]) != jd
            or positivist.to_jd(p[0], p[1], p[2]) != jd or julian.to_jd(j[0], j[1], j[2]) != jd):
        bad += 1
        print("mismatch", g, h, i, c, n, a, p, j)
    if h[2] == 1 or i[2] == 1 or c[2] == 1 or n[2] == 1 or a[2] == 1:
        print(g, "hebrew", h, "islamic", i, "coptic", c, "indian", n, "armenian", a)
    total += h[0] + h[1] + h[2] + i[0] + i[1] + i[2] + c[1] + n[1] + a[1] + p[1] + p[2] + j[2]
print("days", 430, "mismatches", bad, "sum", total)

# every 997th day from the year 1 to 2999 (Armenian and Positivist from their epochs)
bad = 0
total = 0
count = 0
jd = gregorian.to_jd(1, 1, 1)
while jd < gregorian.to_jd(3000, 1, 1):
    g = gregorian.from_jd(jd)
    h = hebrew.from_jd(jd)
    i = islamic.from_jd(jd)
    c = coptic.from_jd(jd)
    n = indian_civil.from_jd(jd)
    j = julian.from_jd(jd)
    o = ordinal.from_jd(jd)
    if (gregorian.to_jd(g[0], g[1], g[2]) != jd or hebrew.to_jd(h[0], h[1], h[2]) != jd
            or islamic.to_jd(i[0], i[1], i[2]) != jd or coptic.to_jd(c[0], c[1], c[2]) != jd
            or indian_civil.to_jd(n[0], n[1], n[2]) != jd or julian.to_jd(j[0], j[1], j[2]) != jd
            or ordinal.to_jd(o[0], o[1]) != jd):
        bad += 1
        print("mismatch", g, h, i, c, n, j, o)
    if jd > armenian.EPOCH + 365:  # its year 0 is out of range for to_jd
        a = armenian.from_jd(jd)
        s = armenian.from_jd(jd, "sarkawag") if jd >= armenian.EPOCH_SARKAWAG else (0, 0, 0)
        if armenian.to_jd(a[0], a[1], a[2]) != jd or (s[0] > 0 and armenian.to_jd(s[0], s[1], s[2], "sarkawag") != jd):
            bad += 1
            print("mismatch", g, a, s)
        total += a[0] + a[1] + a[2] + s[0] + s[1] + s[2]
    if jd >= positivist.EPOCH:
        p = positivist.from_jd(jd)
        if positivist.to_jd(p[0], p[1], p[2]) != jd:
            bad += 1
            print("mismatch", g, p)
        total += p[0] + p[1] + p[2]
    total += g[0] + g[1] + g[2] + h[0] + h[1] + h[2] + i[0] + i[1] + i[2] + c[0] + c[1] + c[2]
    total += n[0] + n[1] + n[2] + j[0] + j[1] + j[2] + o[1]
    count += 1
    jd += 997
print("days", count, "mismatches", bad, "sum", total)

# month lengths, leap years, month calendars
print("hebrew", [hebrew.month_length(5784, mo) for mo in range(1, 14)], hebrew.leap(5784),
      hebrew.leap(5785), hebrew.year_months(5784), hebrew.year_months(5785))
print("islamic", [islamic.month_length(1445, mo) for mo in range(1, 13)], islamic.leap(1445),
      islamic.leap(1446))
print("julian", julian.month_length(1900, 2), julian.month_length(2023, 2), julian.leap(1900),
      julian.leap(2023))
print("gregorian", gregorian.month_length(1900, 2), gregorian.month_length(2000, 2),
      gregorian.month_length(2024, 4), gregorian.legal_date(2024, 2, 29), gregorian.to_jd2(2024, 3, 11))
print("coptic", coptic.month_length(1739, 13), coptic.month_length(1740, 13), coptic.is_leap(1739))
print("indian", [indian_civil.month_length(1946, mo) for mo in range(1, 13)],
      indian_civil.month_length(1945, 1))
print("armenian", armenian.month_length(1473, 13), armenian.month_length(1472, 13, "sarkawag"),
      armenian.leap(1472), armenian.leap(500))
print(gregorian.monthcalendar(2024, 2))
print(julian.monthcalendar(2024, 3))
print(hebrew.monthcalendar(5784, 13))
print(islamic.monthcalendar(1445, 9))
print(coptic.monthcalendar(1739, 13))
print(indian_civil.monthcalendar(1946, 12))
print(armenian.monthcalendar(1473, 13))
print(utils.monthcalendarhelper(6, 31), utils.monthcalendarhelper(5, 28))

# the other calendars and helpers
print("hebrew", hebrew.from_jd(2460000.5), hebrew.to_jd(5784, 13, 29), hebrew.to_civil(5784, 1, 1),
      hebrew.to_jd_gregorianyear(2024, 7, 1), hebrew.delay_1(5784), hebrew.delay_2(5784),
      hebrew.MONTHS[6], hebrew.MONTHS_HEB[6])
print("islamic", islamic.to_jd_gregorianyear(2024, 9, 1), islamic.from_jd(1948439.5),
      islamic.MONTHS[8])
print("armenian", armenian.from_jd(2460000, "sarkawag"), armenian.from_gregorian(2024, 3, 11, "sarkawag"),
      armenian.to_jd(1473, 1, 1, "sarkawag"), armenian.from_julian(2024, 2, 27),
      armenian.to_julian(1473, 7, 11), armenian.MONTHS[12], armenian.MONTHS_ARM[0])
print("positivist", positivist.from_jd(positivist.EPOCH), positivist.to_jd(236, 14, 2),
      positivist.legal_date(236, 14, 2), positivist.weekday(17), positivist.festival(14, 1),
      positivist.festival(3, 14))
print("mayan", mayan.to_jd(13, 0, 0, 0, 0), mayan.from_jd(mayan.EPOCH), mayan.lc_to_haab(9, 12, 11, 5, 18),
      mayan.lc_to_tzolkin(9, 12, 11, 5, 18), mayan.month_length("Wayeb'"), mayan.month_length("Pop"))
print("iso", iso.to_jd(2024, 1, 1), iso.to_gregorian(2020, 53, 7), iso.to_gregorian(2026, 1, 1),
      [iso.weeks_per_year(yy) for yy in (2004, 2009, 2015, 2020, 2021, 2026, 2032)])
print("ordinal", ordinal.to_jd(2024, 366), ordinal.from_jd(2460676.5), ordinal.to_gregorian(1900, 60))
print("julianday", julianday.to_gregorian(2451544.5), julianday.from_gregorian(2000, 1, 1),
      julianday.to_julian(2451544.5), julianday.from_julian(1999, 12, 19))
print("utils", utils.amod(14, 7), utils.amod(15, 7), utils.amod(-1, 7), utils.jwday(2460000.5),
      utils.jwday(2460000))


def weekdays(jd0):  # a float Julian day gives floats, an int one ints
    print(utils.weekday_before(0, jd0), utils.nearest_weekday(3, jd0), utils.next_weekday(6, jd0),
          utils.next_or_current_weekday(2, jd0), utils.previous_weekday(1, jd0),
          utils.previous_or_current_weekday(4, jd0), utils.search_weekday(5, jd0, -1, 2),
          utils.n_weeks(0, jd0, 1), utils.n_weeks(6, jd0, -2), utils.n_weeks(3, jd0, 0))


weekdays(2460000.5)
weekdays(2460000)

# int Julian days, as upstream's own tests pass them (ranges of ints): julian, hebrew, islamic and
# indian_civil rebind jd to a float, which the port does under another name (PORT.md)
for ij in range(113957, 1574957, 182500):
    j = julian.from_jd(ij)
    print(ij, j, julianday.to_julian(ij), julian.to_jd(j[0], j[1], j[2]))
for ij in range(2159677, 2488395, 32000):
    h = hebrew.from_jd(ij)
    i = islamic.from_jd(ij)
    n = indian_civil.from_jd(ij)
    print(ij, h, i, n, hebrew.to_jd(h[0], h[1], h[2]), islamic.to_jd(i[0], i[1], i[2]),
          indian_civil.to_jd(n[0], n[1], n[2]), julian.from_jd(ij))


# error paths
try:
    gregorian.to_jd(2023, 2, 29)
except ValueError as e:
    print("ValueError:", e)
try:
    julian.to_jd(1900, 4, 31)
except ValueError as e:
    print("ValueError:", e)
try:
    hebrew.month_length(5784, 14)
except ValueError as e:
    print("ValueError:", e)
try:
    coptic.month_length(1740, 14)
except ValueError as e:
    print("ValueError:", e)
try:
    armenian.month_length(1473, 14)
except ValueError as e:
    print("ValueError:", e)
try:
    armenian.from_jd(armenian.EPOCH - 1)
except ValueError as e:
    print("ValueError:", e)
try:
    armenian.from_jd(2000000.5, "sarkawag")
except ValueError as e:
    print("ValueError:", e)
try:
    armenian.to_jd(0, 1, 1)
except ValueError:
    print("ValueError for armenian.to_jd(0, 1, 1)")
try:
    armenian.to_jd(600, 13, 6)
except ValueError:
    print("ValueError for armenian.to_jd(600, 13, 6)")
try:
    positivist.to_jd(236, 14, 3)
except ValueError as e:
    print("ValueError:", e)
try:
    positivist.from_jd(2374478.5)
except ValueError as e:
    print("ValueError:", e)
try:
    mayan.from_jd(584281.5)
except ValueError as e:
    print("ValueError:", e)
# CPython's calendar.IllegalMonthError is an IndexError (and a ValueError)
try:
    gregorian.month_length(2023, 13)
except IndexError as e:
    print("IndexError:", e)
try:
    gregorian.monthcalendar(2023, 0)
except LookupError as e:
    print("LookupError:", e)
