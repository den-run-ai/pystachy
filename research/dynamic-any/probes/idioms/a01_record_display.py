# pystachy: dynamic-any
# A heterogeneous record from a dict display, printed, formatted and iterated
rec = {"name": "cpu", "value": 42, "ratio": 0.5, "ok": True, "tags": ["a", "b"], "none": None}
print(rec)
print(f"{rec['name']}={rec['value']} ratio={rec['ratio']:.2f}")
for k, v in rec.items():
    print(k, type(v).__name__, v)
print(len(rec), "value" in rec, rec.get("missing"), rec.get("missing", 0))
