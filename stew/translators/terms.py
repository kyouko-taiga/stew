from collections import OrderedDict
from collections.abc import Mapping

from ..core import generator


class Term(object):

    def __init__(self, prefix, domain=None, args=None):
        # Infer the sort of the term from the codomain of its operator.
        if (domain is None) and hasattr(prefix, 'codomain'):
            domain = prefix.codomain

        args = args or OrderedDict()

        if not isinstance(args, OrderedDict):
            if not hasattr(prefix, 'domain'):
                raise ValueError(
                    "'args' should be an instance of OrderedDict when the "
                    "'prefix' has no 'domain' attribute")

            # If the given args is an a priori unordered mapping, we create an
            # OrderedDict from the definition of the operator's domain.
            if isinstance(args, Mapping):
                args = OrderedDict([(name, args[name]) for name in prefix.domain])

            # If the given args is a sequence, we create an OrderedDict by
            # associating each item name of the operator's domain with its
            # corresponding item in the sequence.
            else:
                args = OrderedDict([(name, value) for name, value in zip(prefix.domain, args)])

        # Infer the sort of the term arguments.
        for name, value in args.items():
            if (value.__domain__ is None) and hasattr(prefix, 'domain'):
                value.__domain__ = prefix.domain[name]

        self.__prefix__ = prefix
        self.__domain__ = domain
        self.__args__ = args


def is_variable(term):
    return not (term.__args__ or isinstance(term.__prefix__, generator))


def variables_of(term):
    if is_variable(term):
        return [term]

    rv = []
    for subterm in term.__args__.values():
        rv += variables_of(subterm)
    return rv


def is_linear(term):
    if not term.__args__:
        return True

    seen = set()
    for v in variables_of(term):
        if v.__prefix__ in seen:
            return False
        seen.add(v.__prefix__)
    return True
