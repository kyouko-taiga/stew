from .core import Attribute, generator
from .matching import Var
from .exceptions import TranslationError


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
                if self.domain is None:
                    raise TranslationError('Cannot infer the type of %s.%s.' % (self.name, name))

                return TermTree(
                    name=getattr(self.domain, name),
                    domain=getattr(self.domain, name).codomain,
                    positional_args=(self,) + args,
                    named_args=kwargs)

            return method

        for name in cls._special_names:
            if name not in attrs:
                attrs[name] = make_method(name)

        return type.__new__(cls, classname, (Var,), attrs)


class TermTree(metaclass=TermTreeType):

    def __init__(self, name, domain=None, positional_args=None, named_args=None):
        self.name = name
        self.domain = domain
        self.positional_args = positional_args or []
        self.named_args = named_args or {}


class TermTreeManager(object):

    def __getattr__(self, name):
        self.__dict__[name] = TermTree(name)
        return self.__dict__[name]
