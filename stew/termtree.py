import inspect

from collections import OrderedDict
from functools import partial
from itertools import zip_longest

from .core import Attribute, generator, operation
from .matching import Var
from .exceptions import TranslationError


def make_term_from_call(attr, *args, **kwargs):
    parameters = inspect.signature(attr.fn).parameters

    if len(args) > len(parameters):
        raise TranslationError(
            '%s() takes %i positional arguments but %i were given.' %
            (attr.fn.__qualname__, len(parameters), len(args)))

    term_args = OrderedDict()
    for arg, parameter in zip_longest(args, parameters):
        term_args[parameter] = arg

    for name, value in kwargs.items():
        if name not in term_args:
            raise TranslationError(
                "%s got an unexpected keyword argument '%s'." %
                (attr.fn.__qualname__, name))
        term_args[name] = value

    missing = []
    for name, value in term_args.items():
        if value is None:
            missing.append(name)
        else:
            # Infer the type of the arguments from the signature.
            value.__domain__ = attr.domain[name]

    if len(missing) > 0:
        raise ArgumentError(
            '%s() missing argument(s): %s' % (attr.fn.__qualname__, ', '.join(missing)))

    return TermTree(prefix=attr, domain=attr.codomain, args=term_args)


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
                if self.__domain__ is None:
                    raise TranslationError(
                        'Cannot infer the type of %s.%s.' % (self.__prefix__, name))

                attr = getattr(self.__domain__, name)
                return make_term_from_call(attr, *((self,) + args), **kwargs)

            return method

        for name in cls._special_names:
            if name not in attrs:
                attrs[name] = make_method(name)

        return type.__new__(cls, classname, (Var,), attrs)


class TermTree(metaclass=TermTreeType):

    def __init__(self, prefix, domain=None, args=None):
        self.__prefix__ = prefix
        self.__domain__ = domain
        self.__args__ = args or OrderedDict()

    def __getattr__(self, name):
        if name == 'where':
            # Return a function that generates the term corresponding to a
            # call to the attribute constructor of the current term.
            term_args = {name: getattr(self, name) for name in self.__domain__.__attributes__}
            def where(**kwargs):
                init_args = dict(term_args)
                init_args.update(kwargs)
                return SortMock(self.__domain__)(**init_args)
            return where

        if name not in self.__domain__.__attributes__:
            raise TranslationError(
                "'%s' has no attribute '%s'." % (self.__domain__.__name__, name))

        return TermTree(
            prefix='%s.__get_%s__' % (self.__domain__.__name__, name),
            domain=getattr(self.__domain__, name).domain,
            args=OrderedDict([('term', self)]))


class TermTreeManager(object):

    def __getattr__(self, name):
        self.__dict__[name] = TermTree(name)
        return self.__dict__[name]


class SortMock(object):

    def __init__(self, target):
        self.__target__ = target

    def __getattr__(self, name):
        attr = getattr(self.__target__, name)
        if isinstance(attr, (generator, operation)):
            # Return a function that generates the term corresponding to a
            # call to the accessed generator or operation.
            return partial(make_term_from_call, attr)

        raise TranslationError(
            'Cannot translate %s because it is not a generator, an operation nor an attribute.')

    def __call__(self, *args, **kwargs):
        positionals = [None] * len(self.__target__.__attributes__)
        positionals[:len(args)] = args

        term_args = OrderedDict()
        missing = []
        for name, value in zip(self.__target__.__attributes__, positionals):
            term_args[name] = value or kwargs.get(name)
            if term_args[name] is None:
                missing.append(name)

        if len(missing) > 0:
            raise TranslationError(
                '%s.__init__() missing argument(s): %s' %
                (self.__target__.__name__, ', '.join(missing)))

        return TermTree(
            prefix=self.__target__.__attr_constructor__,
            domain=self.__target__,
            args=term_args)
