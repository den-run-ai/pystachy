def check(age: int) -> int:
    if age < 0:
        raise ValueError(f"bad age {age}")
    return age
print(check(30))
assert check(1) == 1, "ok"
print(check(-1))
