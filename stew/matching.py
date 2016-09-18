from contextlib import contextmanager
from threading import local

from .exceptions import MatchError


_local_data = local()
_local_data.context_stack = []


def _find_matching_context():
    try:
        return _local_data.context_stack[-1]
    except IndexError:
        return None


@contextmanager
def push_context():
    _local_data.context_stack.append(MatchingContext())
    yield _local_data.context_stack[-1]
    del _local_data.context_stack[-1]


def matches(lhs, rhs):
    if isinstance(lhs, Var):
        raise MatchError('Variables should not appear in lvalues.')

    if isinstance(rhs, Var):
        # If the rhs variable is not bound to any value, we can bind it to the
        # current lhs and we have a match. Otherwise, we should also make sure
        # its bound value is equal to the lhs.
        if isinstance(getattr(var, rhs.name), Var):
            setattr(var, rhs.name, lhs)
            return True
        return lhs.equiv(getattr(var, rhs.name))

    if lhs._is_a_constant or rhs._is_a_constant:
        if not lhs._is_a_constant or not rhs._is_a_constant:
            return False

        if lhs._generator == rhs._generator:
            # If both the lhs and the rhs are constants built with the same
            # generator, we have to match all their generator arguments.
            if lhs._generator_args is None:
                return True

            for name in lhs._generator_args:
                if not matches(lhs._generator_args[name], rhs._generator_args[name]):
                    return False
            return True
        else:
            return False

    if issubclass(lhs.__class__, rhs.__class__):
        # If both the lhs and the rhs are non constant values of the same
        # sort, we have to match their attributes.
        for name in lhs.__class__.__attributes__:
            if not matches(getattr(lhs, name), getattr(rhs, name)):
                return False
        return True

    return False


class MatchingContext(object):

    def __init__(self):
        self.bindings = {}


class Var(object):

    def __init__(self, name):
        self.name = name

    def __eq__(self, other):
        return True


class VarManager(object):

    def __getattr__(self, attr):
        context = _find_matching_context()
        if context is None:
            raise RuntimeError('Working outside of a matching context.')

        if attr not in context.bindings:
            context.bindings[attr] = Var(attr)
        return context.bindings[attr]

    def __setattr__(self, attr, value):
        context = _find_matching_context()
        if context is None:
            raise RuntimeError('Working outside of a matching context.')

        context.bindings[attr] = value


var = VarManager()
