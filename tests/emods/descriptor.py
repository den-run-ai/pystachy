class Named:
    def __set_name__(self, owner: int, name: str) -> None:
        print("named", name)


field = Named()


class Record:
    value = field
