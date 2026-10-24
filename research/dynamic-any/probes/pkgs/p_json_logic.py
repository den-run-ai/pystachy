# pystachy: dynamic-any
from json_logic import jsonLogic
print(jsonLogic({"if": [{">": [{"var": "temp"}, 30]}, "hot", "mild"]}, {"temp": 35}))
print(jsonLogic({"and": [{"==": [{"var": "role"}, "admin"]}, {"<": [{"var": "n"}, 2.5]}]}, {"role": "admin", "n": 1}))
