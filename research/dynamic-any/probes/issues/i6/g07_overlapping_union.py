from datetime import date, datetime


def when(full: bool) -> datetime | date:
    return datetime(2020, 1, 2, 3, 4) if full else date(2020, 1, 2)


print(when(True), when(False))
