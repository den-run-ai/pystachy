# error: cannot infer the type of an empty list; add a type annotation
# an empty list display stored as object: nothing gives its items a type
def main() -> None:
    x: object = []
    print(x)


main()
