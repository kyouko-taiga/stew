import inspect
import ast
import astunparse

from functools import update_wrapper
from types import FunctionType, MethodType

from .exceptions import ArgumentError, RewritingError
from .matching import Var, push_context, matches


undefined = object()


class generator(object):

    def __init__(self, fn):
        # Get the domain and codomain of the generator.
        annotations = dict(fn.__annotations__)
        try:
            self._codomain = annotations.pop('return')
        except KeyError:
            raise SyntaxError('Undefined codomain for %s().' % fn.__qualname__)
        self._domain = annotations
        self.fn = fn

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

    def __str__(self):
        domain = ', '.join(
            '%s:%s' % (name, sort.__sortname__) for name, sort in self.domain.items())
        return '(%s) -> %s' % (domain, self.codomain.__sortname__)


class operation(generator):

    def __init__(self, fn):
        super().__init__(fn)

        if not hasattr(fn, '_original'):
            # Rewrite the operation so that its if statements are wrapped
            # within a matching context.
            node = ast.parse(_unindent(inspect.getsource(fn)))
            node = _RewriteOperation().visit(node)

            src = astunparse.unparse(node)
            exec(compile(src, filename='', mode='exec'))

            self.fn = locals()['_fn']
            update_wrapper(self.fn, fn)
            self.fn.__qualname__ = fn.__qualname__
            self.fn._original = fn

    def __get__(self, instance, owner=None):
        if instance is None:
            return self

        new_mtd = MethodType(self._prepare_fn(), instance)
        return self.__class__(new_mtd)

    def __call__(self, *args, **kwargs):
        # TODO Type checking

        if inspect.ismethod(self.fn):
            fn = self.fn
        else:
            fn = self._prepare_fn()

        rv = fn(*args, **kwargs)
        if rv is None:
            raise RewritingError('Failed to apply %s().' % self.fn.__qualname__)
        return rv

    def _prepare_fn(self):
        fn_globals = dict(self.fn._original.__globals__)
        fn_globals['push_context'] = push_context
        return update_wrapper(FunctionType(self.fn.__code__, fn_globals), self.fn)


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
        return matches(self, other)

    def equiv(self, other):
        if isinstance(other, Var):
            return True

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


def _unindent(src):
    indentation = len(src) - len(src.lstrip())
    return '\n'.join([line[indentation:] for line in src.split('\n')])


class _RewriteOperation(ast.NodeTransformer):

    _push_context_call = ast.parse('push_context()').body[0].value

    def visit_FunctionDef(self, node):

        # We have to rename the function so we're sure its name won't collide
        # with a local variable of operation.__init__. We also have to remove
        # its annotations, so that we don't need to import the sorts of its
        # domain and codomain when we'll recompile it. Finally, we have to
        # remove the function decorators so they don't get executed twice.

        return self._update(
            node,
            name='_fn',
            args=self._update(
                node.args,
                args=[self._update(arg, annotation=None) for arg in node.args.args]),
            body=[self.visit(child) for child in node.body],
            returns=None,
            decorator_list=[])

    def visit_Return(self, node):
        if type(node.value) == ast.IfExp:
            return self._wrap(node)
        return node

    def visit_If(self, node):
        return self._wrap(ast.If(
            test=node.test,
            body=node.body,
            orelse=[self.visit(child) for child in node.orelse]))

    def _wrap(self, node):
        return ast.With(
            items=[ast.withitem(context_expr=self._push_context_call, optional_vars=None)],
            body=[node])

    def _update(self, node, **kwargs):
        return type(node)(**{name: kwargs.get(name, getattr(node, name)) for name in node._fields})
