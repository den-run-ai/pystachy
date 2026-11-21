# error: inheritance from Stack, which derives from list, is not supported
class Stack(list[int]):
    pass


class Deep(Stack):
    pass
