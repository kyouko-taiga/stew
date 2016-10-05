from ..core import generator, attr_constructor, operation

from .translator import Translator


class SimpleTranslator(Translator):

    def dumps(self):
        rv = ''

        for operation in self.axioms:
            for axiom in self.axioms[operation]:
                rv += '%s\n' % dump_axiom(
                    operation=operation,
                    guards=axiom['guards'],
                    matchs=axiom['matchs'],
                    return_value=axiom['return_value'])
            rv += '\n'

        return rv

def dump_axiom(operation, guards, matchs, return_value):
    guard_exprs = []
    for left, op, right in guards:
        op = '==' if op == '__eq__' else '!='
        guard_exprs.append('(%s %s %s)' % (dump_term(left), op, dump_term(right)))
    guard_expr = ' and '.join(guard_exprs)

    match_expr = _nameof(operation) + '('
    for parameter in operation.domain:
        if parameter in matchs:
            match_expr += dump_term(matchs[parameter]) + ', '
        else:
            match_expr += parameter + ', '
    match_expr = match_expr.rstrip(', ') + ')'

    return (
        (guard_expr + ' =>\n\t' if guard_expr else '') +
        match_expr + ' = ' + dump_term(return_value))


def dump_term(term):
    if term.__args__:
        subterms = ', '.join(dump_term(subterm) for subterm in term.__args__.values())
        return _nameof(term.__prefix__) + '(' + subterms + ')'

    return _nameof(term.__prefix__)


def _nameof(prefix):
    if isinstance(prefix, generator):
        if isinstance(prefix, attr_constructor):
            return prefix.codomain.__name__

        if prefix._fn.__name__.startswith('__get_'):
            return prefix.domain['term'].__name__ + '.' + prefix._fn.__name__

        qualname = prefix._fn.__qualname__.split('.')
        if qualname[0] == 'SortBase':
            return prefix._fn.__name__

        if '<locals>' in qualname:
            del qualname[qualname.index('<locals>')]
        return '.'.join(qualname)

    return prefix
