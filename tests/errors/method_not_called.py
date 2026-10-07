# error: TextIOWrapper.close is a method: call it, close(...) (methods are not values)
f = open("/dev/null")
f.close
