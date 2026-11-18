def argument(label: str) -> str:
    print("argument", label)
    return label


def failing() -> str:
    print("failing argument")
    raise ValueError("argument failed")


class C(Exception):
    def zero(self) -> None:
        super().__init__()
        print("zero finished")

    def one_str(self) -> None:
        super().__init__(argument("not a type"))
        print("one_str finished")

    def one_none(self) -> None:
        super().__init__(None)
        print("one_none finished")

    def one_class(self) -> None:
        super().__init__(C)
        print("one_class finished")

    def two_none(self) -> None:
        super().__init__(C, None)
        print("two_none finished")

    def two_child(self) -> None:
        super().__init__(C, Derived("subclass"))
        print("two_child finished")

    def two_subclass(self) -> None:
        super().__init__(C, Derived)
        print("two_subclass finished")

    def two_other(self) -> None:
        super().__init__(C, Other("unrelated"))
        print("two_other finished")

    def two_class(self) -> None:
        super().__init__(C, Other)
        print("two_class finished")


    def three(self) -> None:
        super().__init__(argument("first"), argument("second"), argument("third"))
        print("three finished")

    def raises(self) -> None:
        super().__init__(failing())

    def reassign(self) -> None:
        try:
            super().__init__((self := C("replacement")))
        except TypeError as error:
            print("reassigned", str(error))
        print("local replaced", self is None)


class Derived(C):
    pass


class Other(Exception):
    pass


class Missing(AttributeError):
    def keyword(self) -> None:
        super().__init__(name=argument("name"), obj=argument("obj"))
        print("keyword finished")


for present in [False, True]:
    print("present", present)
    value: C | None = C("original") if present else None
    C.zero(value)
    for shape in range(10):
        try:
            if shape == 0:
                C.one_str(value)
            elif shape == 1:
                C.one_none(value)
            elif shape == 2:
                C.one_class(value)
            elif shape == 3:
                C.two_none(value)
            elif shape == 4:
                C.two_child(value)
            elif shape == 5:
                C.two_subclass(value)
            elif shape == 6:
                C.two_other(value)
            elif shape == 7:
                C.two_class(value)
            elif shape == 8:
                C.three(value)
            else:
                C.raises(value)
        except TypeError as error:
            print("type error", str(error))
        except ValueError as error:
            print("value error", str(error))
    C.reassign(value)
    missing: Missing | None = Missing() if present else None
    try:
        Missing.keyword(missing)
    except TypeError as error:
        print("keyword error", str(error))
