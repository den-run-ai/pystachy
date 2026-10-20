# error: E.__init__() got multiple values for argument 'k'
class E(Exception):
    def __init__(self, k: list[int]) -> None:
        super().__init__(k)


raise E([1], k=[None])
