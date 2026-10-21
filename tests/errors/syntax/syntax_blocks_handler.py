# error: syntax_blocks_handler.py:26: error: too many statically nested blocks
# a generator's code has one block open, and an except handler's body two more
def g(x: list[int]):
    yield 1
    while x:
        while x:
            while x:
                while x:
                    while x:
                        while x:
                            while x:
                                while x:
                                    while x:
                                        while x:
                                            while x:
                                                while x:
                                                    while x:
                                                        while x:
                                                            while x:
                                                                while x:
                                                                    while x:
                                                                        while x:
                                                                            while x:
                                                                                try:
                                                                                    pass
                                                                                except ValueError:
                                                                                    pass
