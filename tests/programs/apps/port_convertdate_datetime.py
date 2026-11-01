# Restored upstream datetime consumers, including ISO year boundaries and naive/aware dates.
from datetime import datetime, timedelta, timezone

from convertdate import gregorian, iso, julian, julianday

for year, month, day in [(1, 1, 1), (2000, 2, 29), (2024, 12, 31), (0, 1, 1), (-1, 6, 15)]:
    print("format", gregorian.format(year, month, day), julian.format(year, month, day))
    # libc differs in padding %Y below year 1000; default formatting covers those dates.
    if year >= 1000:
        print("numeric", gregorian.format(year, month, day, "%Y-%m-%d"))

for year, month, day in [(2015, 12, 31), (2016, 1, 1), (2016, 1, 4),
                         (2020, 12, 31), (2021, 1, 1), (2024, 12, 30)]:
    week = iso.from_gregorian(year, month, day)
    from_day = iso.from_jd(gregorian.to_jd(year, month, day))
    print("iso", (week.year, week.week, week.weekday),
          (from_day.year, from_day.week, from_day.weekday),
          iso.to_gregorian(week.year, week.week, week.weekday))

for jdc in [1721425.5, 2440587.5, 2451545.0, 2460370.5, 2460370.75]:
    value = julianday.to_datetime(jdc)
    print("julian day", jdc, value.isoformat(), julianday.from_datetime(value))

# Keep upstream's offset arithmetic, including its sign and fractional-day rounding.
for value in [datetime(2024, 2, 29), datetime(2024, 2, 29, 12, 30, 15),
              datetime(2024, 2, 29, tzinfo=timezone.utc),
              datetime(2024, 2, 29, 12, 30, tzinfo=timezone(timedelta(hours=5, minutes=30))),
              datetime(2024, 2, 29, 12, 30, tzinfo=timezone(timedelta(hours=-4)))]:
    print("datetime", value.isoformat(), julianday.from_datetime(value))

try:
    iso.from_gregorian(2023, 2, 29)
except ValueError as error:
    print("invalid date", error)
