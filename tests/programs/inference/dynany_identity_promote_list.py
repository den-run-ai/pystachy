# No opt-in here: the python-int gate promotes this entry module independently.
import intidentity

value = int("13000")
items: list[int] = [value, value]
intidentity.keep(items[0])
intidentity.churn()
intidentity.keep(value)
intidentity.check("list display")
items.append(value)
intidentity.keep(items[2])
intidentity.keep(items[1])
intidentity.check("list append")
items[0] = int("13000")
intidentity.keep(items[0])
intidentity.keep(items[1])
intidentity.check("list replacement")
items[0] = items[1]
intidentity.keep(items[0])
intidentity.keep(value)
intidentity.check("list item copy")
intidentity.keep(items.pop())
intidentity.keep(value)
intidentity.check("list pop")
