from .exceptions import MatchError


def matches(term, pattern, match_result):
    if isinstance(pattern, Var):
        if issubclass(term.__class__, pattern.domain):
            # If the variable is not bound to any value, we can bind it to the
            # current term and we have a match. Otherwise, we should also make
            # sure the bound term is equal to the current one.
            if pattern.name not in match_result:
                match_result[pattern.name] = term
                return True
            else:
                return term == match_result[pattern.name]
        return False

    if term._is_a_constant or pattern._is_a_constant:
        if not term._is_a_constant or not pattern._is_a_constant:
            return False

        if term._generator == pattern._generator:
            # If both the term and the pattern are constants built with the
            # same generator, we have to match all their generator arguments.
            if term._generator_args is None:
                return True

            for name in term._generator_args:
                if not matches(
                        term._generator_args[name], pattern._generator_args[name], match_result):
                    return False
            return True
        else:
            return False

    if issubclass(term.__class__, pattern.__class__):
        # If both the term and the pattern are of the same sort, we have to
        # match their attributes.
        for name in term.__class__.__attributes__:
            if not matches(getattr(term, name), getattr(pattern, name), match_result):
                return False
        return True

    return False


class MatchResult(object):

    def __init__(self, **attrs):
        self.__dict__.update(attrs)

    def __getattr__(self, attr):
        if attr not in self.__dict__:
            raise MatchError(attr)

    def __repr__(self):
        return repr(self.__dict__)


class RewritingContext(object):

    def __init__(self):
        self.writable = True
        self.rewritings = set()

class Var(object):

    def __init__(self, name, domain):
        self.name = name
        self.domain = domain

    def __eq__(self, other):
        return isinstance(other, self.domain) or (self is other)
