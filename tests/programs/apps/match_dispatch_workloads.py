from dispatch import Command, apply, evaluate, parse
from workload import inputs, run, verify


print(evaluate(["add:7", "sub:2", "scale:3", "reset:0", "add:-4"]))
print(apply(5, Command("add", -2)), parse("sub:-4").value)
for text in ["scale:0", "reset:1", "unknown:3", "add"]:
    try:
        parse(text)
    except ValueError as error:
        print(str(error))

verify()
for shape in ["mixed", "skewed"]:
    literals, pairs, events = inputs(257, shape)
    for kind in ["literal", "tuple", "dataclass"]:
        matched = run(kind, True, 2, literals, pairs, events)
        conditional = run(kind, False, 2, literals, pairs, events)
        assert matched == conditional
        print(shape, kind, matched)
