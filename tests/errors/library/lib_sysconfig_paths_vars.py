# error: expected dict[str,str] | None, got dict[str,int | str]
# get_paths() and get_path() take the caller's variables as a dict of str. The dict of the
# configuration variables, whose values are int or str, is not one (and it is what the paths
# are expanded with anyway).
import sysconfig

print(sysconfig.get_paths(vars=sysconfig.get_config_vars()))
