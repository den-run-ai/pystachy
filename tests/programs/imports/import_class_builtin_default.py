# A method default reads the class body's constant max, not the builtin (once rejected).
from emods.class_builtin import Limits

print(Limits().get())
