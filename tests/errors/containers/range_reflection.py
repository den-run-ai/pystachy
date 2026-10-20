# error: reflection of a range object is not supported: a range (#486)
print(dir(range(3))[:3])
