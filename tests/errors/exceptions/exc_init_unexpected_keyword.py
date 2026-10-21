# error: E.__init__() got an unexpected keyword argument 'nope'
class E(Exception):
    def __init__(self, k: int) -> None:
        super().__init__(k)


raise E(nope=[None])
