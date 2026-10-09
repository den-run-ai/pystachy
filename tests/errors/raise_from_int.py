# error: exception causes must derive from BaseException
n = 5
raise ValueError("x") from n
