from .core import Sort, Attribute
from .exceptions import ArgumentError


class _Strategy(Sort):

    def __init__(self, fn, **kwargs):
        super().__init__(**kwargs)
        self.fn = fn

    def __call__(self, terms):
        if not isinstance(terms, (set, frozenset)):
            terms = frozenset([terms])

        attributes = {name: getattr(self, name) for name in self.__attributes__}
        rv = set()
        for term in terms:
            term = self.fn(term=term, **attributes)
            if isinstance(term, (set, frozenset)):
                rv |= term
            else:
                rv.add(term)
        return rv


def strategy(*args, **kwargs):
    if args and callable(args[0]):
        return _Strategy(args[0])

    def strategy_factory(fn):
        def __init__(self, **kwargs):
            _Strategy.__init__(self, fn, **kwargs)

        cls_dict = dict(kwargs)
        cls_dict['__init__'] = __init__
        return type(fn.__name__, (_Strategy,), cls_dict)

    return strategy_factory


@strategy
def identity(term):
    return term


class union(_Strategy):

    left = Attribute(domain=Sort)
    right = Attribute(domain=Sort)

    def __init__(self, *operands):
        def fn(left, right, term):
            return left(term) | right(term)

        if len(operands) < 2:
            raise ArgumentError('%s requires at least 2 operands.' % self.__class__.__name__)
        elif len(operands) == 2:
            super().__init__(fn, left=operands[0], right=operands[1])
        else:
            super().__init__(fn, left=operands[0], right=union(*operands[1:]))


class fixpoint(_Strategy):

    def __call__(self, terms):
        if not isinstance(terms, (set, frozenset)):
            terms = frozenset([terms])

        rv = self.fn(terms)
        while rv != terms:
            terms = rv
            rv = self.fn(terms)
        return rv
