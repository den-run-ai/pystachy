try:
    print("got", input())
except EOFError:
    print("EOFError")
except RuntimeError as e:
    print("RuntimeError", e)
