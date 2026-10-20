# hash() of dates, times and timedeltas: equal objects hash alike (the values differ from
# CPython's, whose C type hashes its state's bytes with the per-process hash secret), so they are
# dict keys and set elements.
from datetime import date, datetime, time, timedelta, timezone

print(hash(date(2024, 2, 29)) == hash(date(2024, 2, 29)), len({date(2024, 2, 29), date(2024, 2, 29)}))
seen = {datetime(2024, 1, 1, 12), datetime(2024, 1, 1, 12), datetime(2024, 1, 1, 13)}
print(len(seen), datetime(2024, 1, 1, 12) in seen)
aware = {datetime(2024, 1, 1, 12, tzinfo=timezone.utc): "u"}
print(aware[datetime(2024, 1, 1, 14, tzinfo=timezone(timedelta(hours=2)))])
ts = {time(1, 2): "a", time(1, 2, tzinfo=timezone(timedelta(hours=1))): "b"}
print(ts[time(1, 2)], ts[time(0, 2, tzinfo=timezone.utc)], {timedelta(1): 1}[timedelta(hours=24)])
