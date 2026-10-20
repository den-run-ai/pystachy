# convertdate's holidays (ports/convertdate): US, Jewish, Islamic and Mexican holidays of a few
# years, Easter in the three churches over many years, utils.nth_day_of_month, and the weekdays
# of the calendar stand-in, also for years outside 1..9999.
import convertdate
from convertdate import gregorian, holidays, utils

print("convertdate", convertdate.__version__)
for y in (1939, 1940, 1941, 1999, 2000, 2021, 2022, 2023, 2024, 2100):
    print(y, holidays.new_years(y), holidays.new_years(y, True), holidays.martin_luther_king_day(y),
          holidays.lincolns_birthday(y), holidays.valentines_day(y), holidays.washingtons_birthday(y),
          holidays.washingtons_birthday(y, True), holidays.presidents_day(y), holidays.pulaski_day(y))
    print("  ", holidays.may_day(y), holidays.mothers_day(y), holidays.memorial_day(y),
          holidays.fathers_day(y), holidays.juneteenth(y), holidays.flag_day(y),
          holidays.independence_day(y), holidays.independence_day(y, True), holidays.labor_day(y))
    print("  ", holidays.indigenous_peoples_day(y), holidays.indigenous_peoples_day(y, "canada"),
          holidays.halloween(y), holidays.election_day(y), holidays.veterans_day(y),
          holidays.veterans_day(y, True), holidays.rememberance_day(y), holidays.armistice_day(y),
          holidays.thanksgiving(y), holidays.thanksgiving(y, "canada"))
    print("  ", holidays.christmas_eve(y), holidays.christmas(y), holidays.christmas(y, True),
          holidays.new_years_eve(y), holidays.easter(y), holidays.easter(y, "orthodox"),
          holidays.easter(y, "eastern"))
    print("   jewish", holidays.hanukkah(y), holidays.hanukkah(y, True), holidays.purim(y),
          holidays.purim(y, True), holidays.rosh_hashanah(y), holidays.rosh_hashanah(y, True),
          holidays.yom_kippur(y), holidays.yom_kippur(y, True), holidays.passover(y),
          holidays.passover(y, True))
    print("  ", holidays.shavuot(y), holidays.shavuot(y, True), holidays.sukkot(y),
          holidays.sukkot(y, True), holidays.shemini_azeret(y), holidays.shemini_azeret(y, True),
          holidays.lag_baomer(y), holidays.lag_baomer(y, True), holidays.tu_beshvat(y),
          holidays.tu_beshvat(y, True), holidays.tisha_bav(y), holidays.tisha_bav(y, True))
    print("   islamic", holidays.ramadan(y), holidays.ashura(y), holidays.eid_alfitr(y),
          holidays.eid_aladha(y), "mexican", holidays.dia_constitucion(y),
          holidays.dia_constitucion(y, False), holidays.natalicio_benito_juarez(y),
          holidays.natalicio_benito_juarez(y, False), holidays.dia_independencia(y),
          holidays.dia_revolucion(y))

# Easter: the western church's computus, and the orthodox and eastern churches' on the Julian
# calendar, as Gregorian dates
months = [0, 0, 0, 0, 0, 0]
total = 0
for y in range(1, 3000, 3):
    w = holidays.easter(y)
    o = holidays.easter(y, "orthodox")
    e = holidays.easter(y, "eastern")
    months[w[1]] += 1
    total += w[2] + o[1] * 31 + o[2] + e[1] * 31 + e[2]
    if y % 500 == 1 or y in (1583, 1900, 2008, 2101):
        print(y, w, o, e)
print("easter", months, total, holidays.easter(-4713), holidays.easter(0, "orthodox"))

# observed holidays use calendar.weekday, which counts years outside 1..9999 modulo 400
for y in (-401, -1, 0, 10000, 10001, 123456):
    print(y, holidays.new_years(y, True), holidays.independence_day(y, True),
          holidays.veterans_day(y, True), holidays.christmas(y, True))

# nth_day_of_month: n is 1-5, or 0 for the last; weekdays from Monday = 0
print(utils.nth_day_of_month(5, 0, 9, 2014), utils.nth_day_of_month(0, 0, 9, 2014),
      utils.nth_day_of_month(0, 3, 5, 2024), utils.nth_day_of_month(0, 4, 5, 2024),
      utils.nth_day_of_month(1, 6, 2, 2015), utils.nth_day_of_month(4, 6, 2, 2015),
      utils.nth_day_of_month(5, 3, 2, 2024), utils.nth_day_of_month(0, 3, 2, 2024),
      utils.nth_day_of_month(1, 0, 1, 1))
for n, wd, mo in ((5, 3, 4), (6, 2, 4), (1, 7, 4), (-1, 0, 4), (5, 6, 2), (1, 0, 13), (1, 0, 0)):
    try:
        print(utils.nth_day_of_month(n, wd, mo, 2014))
    except IndexError as e:  # also CPython's calendar.IllegalMonthError, for months 13 and 0
        print("IndexError:", e)
# a float year: calendar.weekday builds a datetime.date, which takes ints only; without the
# observed day, the year passes through
print(holidays.new_years(2023.0), holidays.christmas(2022.0), holidays.independence_day(2021.0))
try:
    holidays.new_years(2023.0, True)
except TypeError as e:
    print("TypeError:", e)
try:
    holidays.thanksgiving(2024.0)
except TypeError as e:
    print("TypeError:", e)
try:
    utils.nth_day_of_month(1, 0, 2, 2024.0)
except TypeError as e:
    print("TypeError:", e)
try:
    gregorian.month_length(2024.0, 2)
except TypeError as e:
    print("TypeError:", e)
try:
    holidays.easter(2024, "coptic")
except ValueError as e:
    print("ValueError:", e)
try:
    holidays.thanksgiving(2024, "mexico")
except NotImplementedError as e:
    print("NotImplementedError:", e)
try:
    holidays.columbus_day(2024)
except DeprecationWarning as e:
    print("DeprecationWarning:", e)
