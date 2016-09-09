import random

from functools import update_wrapper, wraps
from types import FunctionType

from .exc import SortError, StewError
from .proxy import Proxy


class _undefined(object):

    def __str__(self):
        return 'undefined'


undefined = _undefined()


class Generator(Proxy):

    def __init__(self, stew, fn, proxied=undefined):
        super().__init__(proxied=proxied)

        object.__setattr__(self, '_stew', stew)
        object.__setattr__(self, '_args', {})
        object.__setattr__(self, '_fn', fn)

        object.__setattr__(self, 'domain', undefined)
        object.__setattr__(self, 'codomain', undefined)

        annotations = dict(fn.__annotations__)
        if 'return' in annotations:
            self.codomain = annotations.pop('return')
        self.domain = annotations

    def __call__(self, *args, **kwargs):
        # If the generator is of the form () -> type, then we return itself.
        if not self.domain:
            if len(args) or len(kwargs):
                raise StewError('%s takes no argument.' % self)
            return self

        # Return a new generator storing the given arguments.
        proxied = object.__getattribute__(self, '_proxied')
        rv = Generator(self._stew, self._fn, proxied=proxied)

        object.__setattr__(rv, 'domain', self.domain)
        object.__setattr__(rv, 'codomain', self.codomain)

        # If there's a single argument, then we can map it anonymously.
        if (len(self.domain) == 1) and (len(args) > 0):
            # Raise for multiple unamed arguments.
            if len(args) > 1:
                raise StewError('Cannot use more than 1 unamed parameter.')

            name = list(self.domain.keys())[0]
            object.__setattr__(rv, '_args', {name: args[0]})
            return rv

        # Read named arguments.
        generator_args = {}

        for arg in self.domain:
            # Make sure the given arguments match the domain of the generator.
            if arg not in kwargs:
                raise StewError('Missing generator argument: `%s`.' % arg)

            generator_args[arg] = kwargs[arg]

        # TODO Typechecking of the arguments

        object.__setattr__(rv, '_args', generator_args)
        return rv

    def __eq__(self, other):
        if isinstance(other, Variable):
            return self.codomain == other.domain

        if isinstance(other, Generator):
            lhs_proxied = object.__getattribute__(self, '_proxied')
            rhs_proxied = object.__getattribute__(other, '_proxied')

            if lhs_proxied != rhs_proxied:
                return False

            for name in set(self._args) | set(other._args):
                if (name not in self._args) or (name not in other._args):
                    return False
                if self._args[name] != other._args[name]:
                    return False

            return True

        return super().__eq__(other)

    def __str__(self):
        # If there isn't any argument, we just return the generator's name.
        if len(self._args) == 0:
            return self._fn.__qualname__

        # If there's only one argument, we skip the name.
        if len(self._args) == 1:
            value = list(self._args.values())[0]
            return self._fn.__qualname__ + '(%s)' % value

        return self._fn.__qualname__ + '(' + args + ')'


class Operation(object):

    def __init__(self, stew, fn):
        self.stew = stew

        annotations = dict(fn.__annotations__)
        self.fn = fn
        self.codomain = annotations.pop('return')
        self.domain = annotations

    def __get__(self, obj, type=None):
        if obj is None:
            return self

        new_func = self.fn.__get__(obj, type)
        return self.__class__(self.stew, new_func)

    def __call__(self, **kwargs):
        rewritings = self.fn(**kwargs)
        elligible = [rewriting for rewriting, guard in rewritings.items() if guard]

        if elligible:
            return random.choice(elligible)
        return None

    def __str__(self):
        domain = ', '.join('%s:%s' % (name, sort.__name__) for name, sort in self.domain.items())
        return '%s : %s -> %s' % (self.fn.__name__, domain, self.codomain.__name__)


class Attribute(object):

    def __init__(self, stew, sort=undefined, default=undefined):
        self.stew = stew
        self.sort = sort
        self.default = default


class Stew(object):

    def __init__(self):
        self._sorts = {}
        self._generators = {}
        self._operations = {}

    def sort(self, cls):
        # Make sure we didn't already register the given class name.
        if cls.__name__ in self._sorts:
            raise StewError('Duplicate Sort: `%s`.' % cls.__name__)

        # Make sure the given class inherits from `Sort`.
        rv = cls
        if Sort not in cls.__bases__:
            rv = type(cls.__name__, (Sort,) + cls.__bases__, dict(cls.__dict__))

        # Register the new sort under its given class name.
        self._sorts[cls.__name__] = rv
        return rv

    def generator(self, fn):
        self._generators[fn.__qualname__] = Generator(self, fn)
        return self._generators[fn.__qualname__]

    def operation(self, fn):
        self._operations[fn.__qualname__] = Operation(self, fn)
        return self._operations[fn.__qualname__]

    def attribute(self):
        pass


class SortBase(type):

    _recursive_references = {}

    @classmethod
    def __prepare__(metacls, name, bases, **kwargs):
        # Inject the class name in the namespace before its body is executed
        # so that functions annotations can use it to denote morphisms.
        SortBase._recursive_references[name] = Proxy()
        return {name: SortBase._recursive_references[name]}

    def __new__(cls, classname, bases, attrs):
        # Create the sort class.
        new_sort = type.__new__(cls, classname, bases, attrs)

        object.__setattr__(SortBase._recursive_references[classname], '_proxied', new_sort)

        obj = new_sort()
        for name, attr in attrs.items():
            # Set the proxied object of the sort generators.
            if isinstance(attr, Generator):
                attr.codomain = new_sort
                object.__setattr__(attr, '_proxied', obj)

        return new_sort


class Sort(metaclass=SortBase):

    def __init__(self, **kwargs):
        # Initialize sort attributes.
        for name, attr in self.__dict__.items():
            if isinstance(attr, Attribute):
                setattr(self, name, kwargs.get(name, attr.default))


class Variable(object):

    def __init__(self, domain):
        self.domain = domain

    def __str__(self):
        return '$%s' % self.domain.__name__
