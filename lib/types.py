"""
Define names for built-in types that aren't directly accessible as a builtin.
"""
# Pystachy's own module, for CPython 3.13's Lib/types.py, of which it has TracebackType, the class
# of the object a with statement passes to __exit__ (lib/_pystachy_types.py's, which from types
# import TracebackType imports directly), MappingProxyType, a read-only view of a dict
# (lib/_pystachy_mappingproxy.py's mappingproxy), and GenericAlias, for CPython's idiom for a generic class:
# __class_getitem__ = classmethod(GenericAlias) in a class body defines nothing in Pystachy, and the
# class's subscripts are what they are in annotations, but not supported at run time. Its other
# names are CPython's, of what Pystachy does not have (functions, methods, code, frames and modules
# as values, namespaces, dynamic class creation, coroutines): the compiler rejects any use of them,
# as of GenericAlias elsewhere
from _pystachy_types import TracebackType
from _pystachy_mappingproxy import mappingproxy as MappingProxyType
from _pystachy_typenames import (
    AsyncGeneratorType,
    BuiltinFunctionType,
    BuiltinMethodType,
    CapsuleType,
    CellType,
    ClassMethodDescriptorType,
    CodeType,
    CoroutineType,
    DynamicClassAttribute,
    EllipsisType,
    FrameType,
    FunctionType,
    GeneratorType,
    GenericAlias,
    GetSetDescriptorType,
    LambdaType,
    MemberDescriptorType,
    MethodDescriptorType,
    MethodType,
    MethodWrapperType,
    ModuleType,
    NoneType,
    NotImplementedType,
    SimpleNamespace,
    UnionType,
    WrapperDescriptorType,
    _GeneratorWrapper,
    _calculate_meta,
    coroutine,
    get_original_bases,
    new_class,
    prepare_class,
    resolve_bases,
)
