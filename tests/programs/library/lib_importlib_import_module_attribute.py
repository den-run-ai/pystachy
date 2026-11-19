# import_module(".child", __package__) imports the submodule child, whose code runs, also where
# the package has an attribute of that name, which `from . import child` would take instead.
import impmod_attr.caller

print(impmod_attr.caller.VALUE)
