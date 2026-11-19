# importlib.import_module() of a name relative to __package__, in the modules of a package.
import impmod_plug.alpha
import impmod_plug.beta
import impmod_plug.sub.deep

print(impmod_plug.beta.sibling(), impmod_plug.beta.nested(), impmod_plug.sub.deep.up(), impmod_plug.sub.deep.where())
