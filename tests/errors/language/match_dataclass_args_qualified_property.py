# error: class match_attribute_defs.PropertyPoint is not supported: method __match_args__() has a decorator
import match_attribute_defs as models


match models.PropertyPoint(7):
    case models.PropertyPoint(x):
        print("matched", x)
