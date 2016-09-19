from functools import wraps

from .core import Sort, Attribute
from .exceptions import ArgumentError, RewritingError


class Strategy(Sort):
    pass


def set_operation(fn):
    @wraps(fn)
    def wrapper(self, terms):
        if not isinstance(terms, (set, frozenset)):
            terms = set([terms])

        rv = set()
        for term in terms:
            term = fn(self, term)
            if isinstance(term, (set, frozenset)):
                rv |= term
            else:
                rv.add(term)
        return rv

    return wrapper


def make_strategy(fn):
    def __call__(self, term):
        if fn(term) is None:
            print(fn)
        return fn(term)
    return type(fn.__name__, (Strategy,), {'__call__': set_operation(__call__)})()


identity = type('identity', (Strategy,), {'__call__': set_operation(lambda self, term: term)})()


class union(Strategy):

    left = Attribute(domain=Strategy)
    right = Attribute(domain=Strategy)

    def __init__(self, *operands):
        if len(operands) < 2:
            raise ArgumentError('%s requires at least 2 operands.' % self.__class__.__name__)
        elif len(operands) == 2:
            super().__init__(left=operands[0], right=operands[1])
        else:
            super().__init__(left=operands[0], right=union(*operands[1:]))

    def __call__(self, terms):
        if not isinstance(terms, (set, frozenset)):
            terms = set([terms])

        return self.left(terms) | self.right(terms)


class fixpoint(Strategy):

    f = Attribute(domain=Strategy)

    def __call__(self, terms):
        if not isinstance(terms, (set, frozenset)):
            terms = set([terms])

        rv = self.f(terms)
        while rv != terms:
            terms = rv
            rv = self.f(terms)
        return rv


class try_(Strategy):

    f = Attribute(domain=Strategy)

    def __call__(self, terms):
        if not isinstance(terms, (set, frozenset)):
            terms = set([terms])

        rv = set()
        for term in terms:
            try:
                rv |= self.f(term)
            except RewritingError:
                rv.add(term)
        return rv

        try:
            return self.f(terms)
        except RewritingError:
            return terms
