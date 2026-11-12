# error: class patterns require a dataclass without a hierarchy, attribute hooks or custom __match_args__
import match_attribute_defs as models


match models.MethodPoint(7):
    case models.MethodPoint(x):
        print("matched", x)
