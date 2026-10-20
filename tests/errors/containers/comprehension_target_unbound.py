# error: comprehension_target_unbound.py:7: error: 'y' is read before the comprehension's for clause that binds it, where CPython raises UnboundLocalError (not supported)
# A for clause's target d[y] reads the comprehension's own y, which only the clause after it
# binds (not the function's y): CPython raises UnboundLocalError and leaves d unchanged
def main() -> None:
    y = "k"
    d = {"k": 0}
    print([0 for x in [1] for d[y] in [2] for y in ["z"]])
    print(d)


main()
