# No dynamic-any opt-in: the imported helper's open result is observable here.
# Replacing its return with int | T must preserve this accepted identity consumer.
from tomllib._re import RE_NUMBER, match_to_number

number = float("nan")
events: list[str] = []


def reuse(text: str) -> float:
    events.append(text)
    return number


match = RE_NUMBER.match("1.25")
assert match is not None
result = match_to_number(match, reuse)
print(result is number, result is not number)
print(result in [number])
print(events)

# Integer parsing bypasses the float callback and preserves the integer type.
integer_match = RE_NUMBER.match("1024")
assert integer_match is not None
integer = match_to_number(integer_match, reuse)
print(isinstance(integer, int), integer == 1024)
print(events)
