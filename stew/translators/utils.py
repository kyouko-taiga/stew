from collections import OrderedDict

from ..core import generator

from .mocks import TermMock


def copy(term):
    return TermMock(
        prefix=term.__prefix__,
        domain=term.__domain__,
        args=OrderedDict([(p, copy(subterm)) for p, subterm in term.__args__.items()])
    )


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
