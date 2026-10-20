# Dicts of None values filled later (email.charset's CODEC_MAP): T | None values.
CODEC_MAP = {"us-ascii": None}


def add_codec(charset: str, codecname: str) -> None:
    CODEC_MAP[charset] = codecname


add_codec("utf-8", "utf-8")
print(CODEC_MAP, CODEC_MAP.get("us-ascii", "x"), CODEC_MAP.get("latin", "y"))
d = {1: None, 2: None}
d[3] = [1, 2]
print(d, d.get(1), d[3])
s = {"a": None}
print(s.setdefault("b", 1.5), s)
