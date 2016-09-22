from ..core import operation, generator

from .translator import Translator


class SimpleTranslator(Translator):

    def write_rule(self, name, parameters, guard_parts, match_parts, return_value):
        guards = []
        for left, op, right in guard_parts:
            op = '==' if op == '__eq__' else '!='
            guards.append('(%s %s %s)' % (self.write_term(left), op, self.write_term(right)))
        guard = ' and '.join(guards)

        match = name + '('
        for parameter in parameters:
            if parameter in match_parts:
                match += self.write_term(match_parts[parameter]) + ', '
            else:
                match += parameter + ', '
        match = match.rstrip(', ') + ')'

        rule = (guard + ' => ' if guard else '') + match + ' = ' + self.write_term(return_value)
        print(rule)

    def write_term(self, term):
        prefix = term.__prefix__
        if isinstance(prefix, operation):
            prefix = self.operations[prefix]
        elif isinstance(prefix, generator):
            prefix = self.generators[prefix]

        if term.__args__:
            subterms = ', '.join(self.write_term(subterm) for subterm in term.__args__.values())
            return prefix + '(' + subterms + ')'

        return prefix
