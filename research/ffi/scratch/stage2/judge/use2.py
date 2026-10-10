import viajson
assert viajson.__file__.endswith(".so")
print(viajson.roundtrip('{"a": [1, 2, {"b": null}]}'))
print(viajson.total("cb", "sq", 1000))
for s in ["[1", "2.5"]:
    try:
        print(viajson.strict(s))
    except (ValueError, TypeError) as e:
        print("caught", type(e).__name__, e)
