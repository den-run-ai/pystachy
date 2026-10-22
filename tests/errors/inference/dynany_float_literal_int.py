# error: expected int, got float
# pystachy: dynamic-any
# A fixed annotation must retain its normal diagnostic instead of parsing float bits as int.
def assign() -> None:
    value: int = 3
    value = 2.5
    print(value)


assign()
