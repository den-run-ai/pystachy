# error: got dict[str,int]
# An explicit method return annotation remains a contract for every call.
class Factory:
    def mapping(self, value) -> dict[str, int]:
        return {}


result: dict[tuple[str, int], int] = Factory().mapping(1)
