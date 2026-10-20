# A finally block nested 8 deep in finally blocks, left by return and raise: each is compiled once
# (copied for each way out, they would grow as 3**8).
def f(n: int) -> int:
    c = 0
    try:
        c += 1
        if n == 3:
            return c
    finally:
        try:
            c += 1
            if n == 3:
                return c
        finally:
            try:
                c += 1
                if n == 3:
                    return c
            finally:
                try:
                    c += 1
                    if n == 3:
                        return c
                finally:
                    try:
                        c += 1
                        if n == 3:
                            return c
                    finally:
                        try:
                            c += 1
                            if n == 3:
                                return c
                        finally:
                            try:
                                c += 1
                                if n == 3:
                                    return c
                            finally:
                                try:
                                    c += 1
                                    if n == 3:
                                        return c
                                finally:
                                    c += 1
                                    if n == 1:
                                        return c
                                    if n == 2:
                                        raise ValueError('x')
    return c
for n in range(4):
    try:
        print(f(n))
    except ValueError as e:
        print('VE', e)
