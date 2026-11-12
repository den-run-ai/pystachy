def total(items: list[int]) -> int:
	result = 0
	for item in items:
		if item > 1:
			result += item
		else:
			result -= 1
	return result


class Box:
	def __init__(self, value: int) -> None:
		self.value = value

	def double(self) -> int:
		# a comment line, then a blank one of spaces and a tab
  	
		return self.value * 2


def mixed(flag: bool) -> str:
	if flag:
	    return "four spaces after a tab"
	return "tab"


def spaces(flag: bool) -> str:
    if flag:
        return "eight spaces"
    return "four"


print(total([1, 2, 3]), Box(4).double(), mixed(True), mixed(False), spaces(True), spaces(False))
values = [
	1,
  2,
]
print(values)
if values:
	print("tab at module level")
