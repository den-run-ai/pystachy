# An imported class's default reads its class's earlier constant over its module's global (once rejected).
from emods.class_attr import C

print(C().b)
