from .matching import Var


class TermTreeType(type):

    _special_names = [
        '__abs__', '__add__', '__and__', '__call__', '__contains__',
        '__delattr__', '__delitem__', '__delslice__', '__divmod__',
        '__floordiv__', '__ge__', '__getitem__', '__getslice__', '__gt__',
        '__iadd__', '__iand__', '__ifloordiv__', '__ilshift__', '__imod__',
        '__imul__', '__index__', '__invert__', '__ior__', '__ipow__',
        '__irshift__', '__isub__', '__iter__', '__itruediv__', '__ixor__',
        '__le__', '__len__', '__lshift__', '__lt__', '__mod__', '__mul__',
        '__ne__', '__neg__', '__or__', '__pos__', '__pow__', '__radd__',
        '__rand__', '__rdiv__', '__rdivmod__', '__reversed__',
        '__rfloorfiv__', '__rlshift__', '__rmod__', '__rmul__', '__ror__',
        '__rpow__', '__rrshift__', '__rshift__', '__rsub__', '__rtruediv__',
        '__rxor__', '__setitem__', '__setslice__', '__sub__', '__truediv__',
        '__xor__'
    ]

    def __new__(cls, classname, bases, attrs):
        def make_method(name):
            def method(self, *args, **kwargs):
                return TermTree(name, (self,) + args, kwargs)
            return method

        for name in cls._special_names:
            if name not in attrs:
                attrs[name] = make_method(name)

        return type.__new__(cls, classname, (Var,), attrs)


class TermTree(metaclass=TermTreeType):

    def __init__(self, name, positional_arguments=None, named_arguments=None):
        self.name = name
        self.positional_arguments = positional_arguments or []
        self.named_arguments = named_arguments or {}


class TermTreeManager(object):

    def __getattr__(self, name):
        self.__dict__[name] = TermTree(name)
        return self.__dict__[name]
