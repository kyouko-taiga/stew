from contextlib import contextmanager
from functools import update_wrapper

from .exceptions import ArgumentError, MatchError, RewritingError
from .proxy import Proxy
from .rewriting import MatchResult, RewritingContext, Var, matches


undefined = object()


class Stew(object):

    def __init__(self):
        self.sorts = {}
        self.generators = {}
        self.operations = {}

        self._rewriting_context = None

    @property
    @contextmanager
    def rewriting_context(self):
        self._rewriting_context = RewritingContext()
        yield self._rewriting_context
        self._rewriting_context = None

    @contextmanager
    def matches(self, *args):
        if self._rewriting_context is None:
            raise RuntimeError('Working outside of a rewriting context.')

        match_result = {}
        for term, pattern in args:
            self._rewriting_context.writable = matches(term, pattern, match_result)
        try:
            yield MatchResult(**match_result)
        except MatchError:
            pass
        self._rewriting_context.writable = True

    @contextmanager
    def if_(self, condition):
        if self._rewriting_context is None:
            raise RuntimeError('Working outside of a rewriting context.')

        self._rewriting_context.writable = condition() if callable(condition) else condition
        yield
        self._rewriting_context.writable = True

    def sort(self, cls):
        # Make sure we didn't already register the given class name.
        if cls.__name__ in self.sorts:
            raise SyntaxError('Duplicate Sort: `%s`.' % cls.__name__)

        # Create a new that references this stew.
        cls_dict = dict(dict(cls.__dict__))
        cls_dict['stew'] = self

        for attr in cls_dict.values():
            if isinstance(attr, operation):
                attr.stew = self

                # Register all generators and references.
                if isinstance(attr, generator):
                    self.generators[attr.fn.__qualname__] = attr
                else:
                    self.operations[attr.fn.__qualname__] = attr

        new_cls = type(cls.__name__, cls.__bases__, cls_dict)

        # Register the new sort under its given class name.
        self.sorts[new_cls.__name__] = new_cls
        return new_cls

    def generator(self, fn):
        self.generators[fn.__qualname__] = generator(fn, self)
        return self.generators[fn.__qualname__]

    def operation(self, fn):
        self.operations[fn.__qualname__] = operation(fn, self)
        return self.operations[fn.__qualname__]


class operation(object):

    def __init__(self, fn, stew=None):
        self.fn = fn
        self.stew = stew

        # Get the domain and codomain of the generator.
        annotations = dict(fn.__annotations__)
        try:
            self.codomain = annotations.pop('return')
        except KeyError:
            raise SyntaxError('Undefined codomain for %s.' % fn.__name__)
        self.domain = annotations

    def __get__(self, instance, owner=None):
        if instance is None:
            return self

        new_fn = self.fn.__get__(instance, owner)
        return self.__class__(new_fn, self.stew)

    def __call__(self, *args, **kwargs):
        # TODO Type checking

        if self.stew is None:
            raise RuntimeError(
                'Undefined stew. Did you forget to decorate %s()?' %
                self.fn.__qualname__)

        with self.stew.rewriting_context as context:
            for item in self.fn(*args, **kwargs):
                if context.writable:
                    return item

            raise RewritingError('Failed apply %s.' % self.fn.__name__)

    def __str__(self):
        domain = ', '.join('%s:%s' % (name, sort.__name__) for name, sort in self.domain.items())
        return '(%s) -> %s' % (domain, self.codomain.__name__)


class generator(operation):

    def __call__(self, *args, **kwargs):
        # Initialize all sorts arguments with `undefined`.
        sort_kwargs = {name: undefined for name in self.codomain.__attributes__}
        rv = self.codomain(**sort_kwargs)
        rv._generator = self

        # If the domain of the generator is empty, make sure no argument
        # were passed to the function.
        if len(self.domain) == 0:
            if (len(args) > 0) or (len(kwargs) > 0):
                raise ArgumentError('%s() takes no arguments.' % self.fn.__name__)
            return rv

        # Allow to call generators with a single positional argument.
        if (len(self.domain) == 1) and (len(args) == 1):
            kwargs.update([(list(self.domain.keys())[0], args[0])])

        # Look for the generator arguments.
        rv._generator_args = {}
        missing = []
        for name, sort in self.domain.items():
            try:
                value = kwargs[name]
            except KeyError:
                missing.append(name)
                continue

            if not (isinstance(value, Var) or isinstance(value, sort)):
                raise ArgumentError(
                    "'%s' should be a variable or a term of sort '%s'." % (name, sort.__name__))

            rv._generator_args[name] = kwargs[name]

        if len(missing) > 0:
            raise ArgumentError(
                '%s() missing argument(s): %s' % (self.fn.__name__, ', '.join(missing)))

        return rv


class Attribute(object):

    def __init__(self, domain, default=None):
        self.domain = domain
        self.default = default


class SortBase(type):

    _recursive_references = {}

    @classmethod
    def __prepare__(metacls, name, bases, **kwargs):
        # Inject the class name in the namespace before its body is executed
        # so that annotations can use it to denote morphisms and generators.
        SortBase._recursive_references[name] = Proxy()
        return {name: SortBase._recursive_references[name]}

    def __new__(cls, classname, bases, attrs):
        # Register class attributes.
        sort_attributes = []
        for name, attr in attrs.items():
            if isinstance(attr, Attribute):
                sort_attributes.append(name)
        attrs['__attributes__'] = tuple(sort_attributes)

        # Create the sort class and bind recursive references.
        new_sort = type.__new__(cls, classname, bases, attrs)
        object.__setattr__(SortBase._recursive_references[classname], '__proxied__', new_sort)

        return new_sort


class Sort(metaclass=SortBase):

    def __init__(self, **kwargs):
        self._generator = None
        self._generator_args = None

        # Initialize the instance attribute.
        missing = []
        for name in self.__attributes__:
            attribute = getattr(self.__class__, name)
            value = kwargs.get(name, attribute.default)
            if value is None:
                missing.append(name)
                continue

            if not (isinstance(value, Var) or isinstance(value, attribute.domain)):
                raise ArgumentError(
                    "'%s' should be a variable or a term or of sort '%s'." %
                    (name, attribute.domain.__name__))

            setattr(self, name, value)

        if len(missing) > 0:
            raise ArgumentError(
                '%s() missing argument(s): %s' % (self.__class__.__name__, ', '.join(missing)))

    @property
    def _is_a_constant(self):
        return self._generator is not None

    def matches(self, pattern):
        if not hasattr(self, 'stew'):
            raise RuntimeError(
                'Undefined stew. Did you forget to decorate %s in module %s?' %
                (self.__class__.__name__, self.__class__.__module__))

        return self.stew.matches((self, pattern))

    def where(self, **kwargs):
        return self.__class__(
            **{name: kwargs.get(name, getattr(self, name)) for name in self.__attributes__})

    def __hash__(self):
        if self._is_a_constant:
            if self._generator_args is None:
                return hash(self._generator)
            return hash(
                (self._generator, ) +
                tuple((name, term) for name, term in self._generator_args.items()))

        return hash(tuple((name, getattr(self, name)) for name in self.__attributes__))

    def __eq__(self, other):
        if self._is_a_constant:
            if (self._generator != other._generator):
                return False
            if self._generator_args is None:
                return True
            keys = self._generator_args.keys()
            return all(self._generator_args[n] == other._generator_args[n] for n in keys)

        return all(getattr(self, name) == getattr(other, name) for name in self.__attributes__)

    def __str__(self):
        if self._is_a_constant:
            if self._generator_args is None:
                return self._generator.fn.__name__
            else:
                args = ['%s: %s' % (name, term) for name, term in self._generator_args.items()]
                args = ', '.join(args)
                return self._generator.fn.__name__ + '(' + args + ')'
        else:
            if len(self.__attributes__) == 0:
                return self.__class__.__name__
            else:
                args = ['%s = %s' % (name, getattr(self, name)) for name in self.__attributes__]
                args = ', '.join(args)
                return self.__class__.__name__ + '(' + args + ')'

    def __repr__(self):
        return repr(str(self))
