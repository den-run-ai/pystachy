# No opt-in here: the python-int gate promotes only this caller, not plaincells.
import intidentity
import plaincells

value = int("16000")
reader = plaincells.capture_pair(value, -value)
intidentity.churn()
reader()
read_identity = plaincells.capture_identity(value)
intidentity.keep(value)
intidentity.churn()
read_identity()
intidentity.check("generic captured identity")
