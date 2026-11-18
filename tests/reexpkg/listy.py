# Re-exports reexpkg.consts' list, then imports reexpkg.readlist, which imports this module back
from reexpkg.consts import ITEMS
import reexpkg.readlist
