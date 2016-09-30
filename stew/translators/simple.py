from ..core import operation, generator

from .translator import Translator


class SimpleTranslator(Translator):

    def dumps(self):
        rv = ''

        for axiom_name in self.axioms:
            for axiom in self.axioms[axiom_name]:
                rv += '%s\n' % self.dump_axiom(
                    name=axiom_name,
                    parameters=axiom['parameters'],
                    guards=axiom['guards'],
                    matchs=axiom['matchs'],
                    return_value=axiom['return_value'])
            rv += '\n'

        return rv

    def dump_axiom(self, name, parameters, guards, matchs, return_value):
        guards = []
        for left, op, right in guards:
            op = '==' if op == '__eq__' else '!='
            guards.append('(%s %s %s)' % (self.dump_term(left), op, self.dump_term(right)))
        guard = ' and '.join(guards)

        match = name + '('
        for parameter in parameters:
            if parameter in matchs:
                match += self.dump_term(matchs[parameter]) + ', '
            else:
                match += parameter + ', '
        match = match.rstrip(', ') + ')'

        return (guard + ' => ' if guard else '') + match + ' = ' + self.dump_term(return_value)

    def dump_term(self, term):
        prefix = term.__prefix__
        if isinstance(prefix, operation):
            prefix = self.operations[prefix]
        elif isinstance(prefix, generator):
            prefix = self.generators[prefix]

        if term.__args__:
            subterms = ', '.join(self.dump_term(subterm) for subterm in term.__args__.values())
            return prefix + '(' + subterms + ')'

        return prefix
