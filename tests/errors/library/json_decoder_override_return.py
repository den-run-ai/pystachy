# error: overrides of JSONDecoder.raw_decode() return incompatible types; use a common return type
# Reject incompatible virtual return layouts instead of skipping the override.
import json


class Decoder(json.JSONDecoder):
    def raw_decode(self, s: str, idx: int = 0) -> tuple[int, int]:
        return 42, len(s)


def through_base(decoder: json.JSONDecoder):
    return decoder.decode("null")


print(through_base(Decoder()))
