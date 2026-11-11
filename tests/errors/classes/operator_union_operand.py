# error: comparing closed union values requires narrowing with isinstance() first
class Left:
    def __eq__(self, other):
        return True


class Other:
    pass


class Right:
    def __eq__(self, other):
        return False


def choose(flag: bool) -> Left | Other:
    return Left() if flag else Other()


print(choose(True) == Right())
