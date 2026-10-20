# format(None, spec) and an f-string field of None evaluate a computed spec, as for any value: None
# formats with an empty spec, and a non-empty one raises CPython's TypeError once the spec has run
def spec(s: str) -> str:
    print("spec evaluated:", repr(s))
    return s


try:
    print(format(None, spec("5")))
except TypeError as e:
    print("TypeError:", e)
try:
    print(f"{None:{spec('>5')}}")
except TypeError as e:
    print("TypeError:", e)
print(format(None, spec("")), f"[{None:{spec('')}}]")
