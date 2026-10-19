# type(e) of an exception is its class's class object, which `is` compares with a class
try:
    open("/nonexistent_q")
except OSError as e:
    print(type(e) is FileNotFoundError)
