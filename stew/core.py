import inspect

from contextlib import contextmanager
from functools import update_wrapper

from .exceptions import ArgumentError, RewritingError
from .rewriting import Var, matches, push_context


undefined = object()


class operation(object):

    def __init__(self, fn):
        self.fn = fn
        self._rewriting_context = None

        # Get the domain and codomain of the generator.
        annotations = dict(fn.__annotations__)
        try:
            self._codomain = annotations.pop('return')
        except KeyError:
            raise SyntaxError('Undefined codomain for %s().' % fn.__qualname__)
        self._domain = annotations

    @property
    def domain(self):
        fn_cls = _function_class(self.fn)
        return {
            name: fn_cls if sort is SortBase.recursive_reference else sort
            for name, sort in self._domain.items()
        }

    @property
    def codomain(self):
        fn_cls = _function_class(self.fn)
        return fn_cls if self._codomain is SortBase.recursive_reference else self._codomain

    def __get__(self, instance, owner=None):
        if instance is None:
            return self

        new_fn = self.fn.__get__(instance, owner)
        return self.__class__(new_fn)

    def __call__(self, *args, **kwargs):
        # TODO Type checking

        with push_context() as context:
            for item in self.fn(*args, **kwargs):
                if context.writable:
                    return item

            raise RewritingError('Failed to apply %s().' % self.fn.__qualname__)

    def __str__(self):
        domain = ', '.join(
            '%s:%s' % (name, sort.__sortname__) for name, sort in self.domain.items())
        return '(%s) -> %s' % (domain, self.codomain.__sortname__)


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
                raise ArgumentError('%s() takes no arguments.' % self.fn.__qualname__)
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
                    "'%s' should be a variable or a term of sort '%s'." %
                    (name, sort.__sortname__))

            rv._generator_args[name] = kwargs[name]

        if len(missing) > 0:
            raise ArgumentError(
                '%s() missing argument(s): %s' % (self.fn.__qualname__, ', '.join(missing)))

        return rv


class Attribute(object):

    def __init__(self, domain, default=None):
        self.domain = domain
        self.default = default


class SortBase(type):

    recursive_reference = object()

    @classmethod
    def __prepare__(metacls, name, bases, **kwargs):

        # To handle recursive references in sort definitions, we need to get
        # the class in which functions that use such references we defined
        # lazily. However, since sorts can be dynamically specialized, we
        # can't simply inject the reference to the newly created class just
        # after we built it in the metaclass, otherwise inherited class will
        # wrongly reference their parent.
        # So as to tackle this issue, we set those recursive references to
        # `SortBase.recursive_reference`, so that we can later compute the
        # class it should refer to.

        return {name: SortBase.recursive_reference}

    def __new__(cls, classname, bases, attrs):
        # Register class attributes.
        sort_attributes = []
        for name, attr in attrs.items():
            if isinstance(attr, Attribute):
                sort_attributes.append(name)
        attrs['__attributes__'] = tuple(sort_attributes)

        # Give a default __sortname__ if none was specified.
        if not '__sortname__' in attrs:
            attrs['__sortname__'] = classname

        # Create the sort class.
        new_sort = type.__new__(cls, classname, bases, attrs)

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
                    (name, attribute.domain.__sortname__))

            setattr(self, name, value)

        if len(missing) > 0:
            raise ArgumentError(
                '%s() missing argument(s): %s' % (self.__class__.__qualname__, ', '.join(missing)))

    @property
    def _is_a_constant(self):
        return self._generator is not None

    def matches(self, pattern):
        return matches((self, pattern))

    def where(self, **kwargs):
        return self.__class__(
            **{name: kwargs.get(name, getattr(self, name)) for name in self.__attributes__})

    @classmethod
    def specialize(cls, sortname=None, **implementations):
        abstract_names = sorted(implementations.keys())

        sortname = sortname or (
            cls.__name__ + '_specialized_with_' +
            '_'.join(implementations[n].__sortname__ for n in abstract_names))

        specialization_dict = dict(cls.__dict__)
        specialization_dict['__sortname__'] = sortname
        for name in abstract_names:
            specialization_dict[name] = implementations[name]

        return SortBase(sortname, (cls,), specialization_dict)

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
                return self._generator.fn.__qualname__
            else:
                args = ['%s: %s' % (name, term) for name, term in self._generator_args.items()]
                args = ', '.join(args)
                return self._generator.fn.__qualname__ + '(' + args + ')'
        else:
            if len(self.__attributes__) == 0:
                return self.__class__.__qualname__
            else:
                args = ['%s = %s' % (name, getattr(self, name)) for name in self.__attributes__]
                args = ', '.join(args)
                return self.__class__.__qualname__ + '(' + args + ')'

    def __repr__(self):
        return repr(str(self))


def _function_class(fn):

    # This function allows us to retrieve the class that defined the given
    # method. It relies on parsing it's __qualname__, which is usually
    # strongly discouraged. However we can't use it's __self__ because
    # generators aren't considered methods by inspect.ismethod.

    cls = getattr(
        inspect.getmodule(fn),
        fn.__qualname__.split('.<locals>', 1)[0].rsplit('.', 1)[0])

    if isinstance(cls, type):
        return cls
    return None
