# pystachy: dynamic-any
# sorting, filtering and aggregating a list of mixed records
rows = [
    {"city": "Oslo", "temp": 3, "note": None},
    {"city": "Rome", "temp": 21.5, "note": "warm"},
    {"city": "Lima", "temp": 18, "note": "fog"},
]
rows.sort(key=lambda r: r["temp"])
print([r["city"] for r in rows])
print(max(rows, key=lambda r: r["temp"])["city"])
print(sum(r["temp"] for r in rows))
print([r["city"] for r in rows if r["note"] is not None])
