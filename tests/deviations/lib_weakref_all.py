# weakref's __all__ leaves out the names it does not have here: proxy, ProxyType,
# CallableProxyType, ProxyTypes, getweakrefcount, getweakrefs and finalize
# (lib/compatibility.md#weakref)
import weakref

print(sorted(weakref.__all__))
