from functools import update_wrapper
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

    def __call__(self, **kwargs):
        # If the generator is of the form () -> type, then we return itself.
        if not self.domain:
            return self

        # Return a new generator storing the given arguments.
        rv = Generator(self._stew, self._fn, proxied=self._proxied)
        generator_args = {}

        for arg in self.domain:
            # Make sure the given arguments match the domain of the generator.
            if arg not in kwargs:
                raise StewError('Missing generator argument: `%s`.' % arg)
            if not isinstance(kwargs[arg], self.domain[arg]):
                raise SortError(
                    '`%s` should have sort `%s`, not `%s`.' %
                    (arg, self.domain[arg], kwargs[arg].__class__))

            generator_args[arg] = kwargs[arg]

        object.__setattr__(rv, 'domain', self.domain)
        object.__setattr__(rv, 'codomain', self.codomain)
        object.__setattr__(rv, '_args', generator_args)

        return rv

    def __eq__(self, other):
        return (
            isinstance(other, Generator) and
            (other._proxied == self._proxied) and
            all(other._args[name] == self._args[name] for name in self._args))

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
        self.name = fn.__name__
        self.codomain = annotations.pop('return')
        self.domain = annotations

    def __str__(self):
        domain = ', '.join('%s:%s' % (name, sort.__name__) for name, sort in self.domain.items())
        return '%s : %s -> %s' % (self.name, domain, self.codomain.__name__)


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

    recursive_reference = object()

    @classmethod
    def __prepare__(metacls, name, bases, **kwargs):
        # Inject the class name in the namespace before its body is executed
        # so that functions annotations can use it to denote morphisms.
        return {name: SortBase.recursive_reference}

    def __new__(cls, classname, bases, attrs):
        # Create the sort class.
        new_sort = type.__new__(cls, classname, bases, attrs)

        for name, attr in attrs.items():
            # Replace the self references in the sort attributes.
            if hasattr(attr, 'domain'):
                for x in attr.domain:
                    if attr.domain[x] is SortBase.recursive_reference:
                        attr.domain[x] = new_sort
            if hasattr(attr, 'codomain'):
                if attr.codomain is SortBase.recursive_reference:
                     attr.codomain = new_sort

            # Set the proxied object of the sort generators.
            if isinstance(attr, Generator):
                attr.codomain = new_sort
                attr._proxied = new_sort()

        return new_sort


class Sort(metaclass=SortBase):

    def __init__(self, **kwargs):
        # Initialize sort attributes.
        for name, attr in self.__dict__.items():
            if isinstance(attr, Attribute):
                setattr(self, name, kwargs.get(name, attr.default))
