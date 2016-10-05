import inspect

from collections import OrderedDict
from functools import reduce
from operator import add

from jinja2 import Environment, FileSystemLoader

from ..core import Sort, generator, attr_constructor, operation
from ..settings import TEMPLATES_DIRECTORY
from ..types.bool import Bool

from .mocks import SortMock, TermMock
from .translator import Translator


true = TermMock(prefix=Bool.true)
false = TermMock(prefix=Bool.false)


class Rule(object):

    def __init__(self, left, right):
        self.left = left
        self.right = right

    def linearize(self):
        pass


class StratagemTranslator(Translator):

    def __init__(self, adt=None):
        super().__init__()

        self.adt = adt or 'stew'

        self.names = {}
        self.variables = {}
        self.next_variable_id = 0

        self.eqs = {}
        self.nes = {}

        self.rules = {}

    def pre_translate(self):
        self.register(Bool)
        self.register_cmp_operations()

    def post_translate(self):
        self.make_basic_rules()

        for operation in self.rules:
            print(self.nameof(operation))
            for rule in self.rules[operation]:
                print('\t' + self.dump_term(rule.left) + ' = ' + self.dump_term(rule.right))

        exit()

    def register_cmp_operations(self):
        for sort in self.sorts:
            @operation
            def eq(left: sort, right: sort) -> Bool:
                if left == right:
                    return Bool.true()
                return Bool.false()

            @operation
            def ne(left: sort, right: sort) -> Bool:
                return ~eq(left, right)

            self.eqs[sort] = eq
            self.nes[sort] = ne

            self.register(eq)
            self.register(ne)

    def make_basic_rules(self):
        for operation in self.axioms:
            self.rules[operation] = []

            # Collect all the guards associated with the axiom group.
            guards = reduce(add, (axiom['guards'] for axiom in self.axioms[operation]))

            # If the axioms don't use any guard, then we can translate
            # directly into basic rewriting rules.
            if not guards:
                for axiom in self.axioms[operation]:
                    self.rules[operation].append(Rule(
                        left=TermMock(
                            prefix=operation,
                            domain=operation.codomain,
                            args=OrderedDict(self.make_pattern(operation, axiom))),
                        right=axiom['return_value']))
                continue

            # Because strategem doesn't support guards on rewriting rules, we
            # have to rewrite axioms that use guards so that they only rely on
            # pattern matching instead.
            # In order to do that, we'll create a new "flattened" rule whose
            # left term is that of the original axiom extended with a "true"
            # subterm for each guard that the axiom checks, so that they get
            # evaluated by pattern matching, while the right term of this
            # so-called "flattened" rule will be that of the original axiom.
            # Finally, we'll replace the right term of the original axiom with
            # a call to the "flattened" rule.

            guard_start = 0
            vterm = lambda n, s: TermMock(prefix='%s' % n, domain=s)

            left_args = [(name, vterm(name, sort)) for name, sort in operation.domain.items()]
            original = Rule(
                left=TermMock(
                    prefix=operation,
                    domain=operation.codomain,
                    args=OrderedDict(left_args)),
                right=TermMock(
                    prefix=self.nameof(operation) + '_flattened',
                    domain=operation.codomain,
                    args=OrderedDict(
                        [('g%i' % i, false) for i in range(len(guards))] + left_args)))

            for axiom in self.axioms[operation]:
                flattened = Rule(
                    left=TermMock(
                        prefix=self.nameof(operation) + '_flattened',
                        domain=operation.codomain,
                        args=OrderedDict(
                            [('g%i' % i, vterm('__%i__' % i, Bool)) for i in range(len(guards))] +
                            self.make_pattern(operation, axiom))),
                    right=axiom['return_value'])

                for i, guard in enumerate(axiom['guards']):
                    op = (self.eqs if guard[1] == '__eq__' else self.nes)[guard[0].__domain__]
                    term = TermMock(
                        prefix=op,
                        domain=Bool,
                        args=OrderedDict([('left', guard[0]), ('right', guard[2])]))

                    guard_name = 'g%i' % (i + guard_start)
                    flattened.left.__args__[guard_name] = true
                    original.right.__args__[guard_name] = term

                self.rules[operation].append(flattened)

                # Since we concatenated all guards in one big list, we have to
                # keep track of the position of the first guard used by the
                # axiom we're considering to corretly set the pattern to match.
                guard_start += len(axiom['guards'])

            self.rules[operation].append(original)

    def make_pattern(self, operation, axiom):
        rv = []
        for name, sort in operation.domain.items():
            if name in axiom['matchs']:
                rv.append((name, axiom['matchs'][name]))
            else:
                rv.append((name, TermMock(prefix=name, domain=sort)))
        return rv


    def register_eq_axioms(self, sort):
        def make_eq_axiom(lhs, rhs, sort):
            return {
                'parameters': OrderedDict([('lhs', sort), ('rhs', sort)]),
                'guards': [],
                'matchs': {'lhs': lhs, 'rhs': rhs},
                'return_value': true
            }

        eqs = []
        for name, attr in sort.__dict__.items():
            if isinstance(attr, generator) and not isinstance(attr, operation):
                parameters = inspect.signature(attr.fn).parameters

                if attr.domain:
                    operands = [
                        TermMock(
                            prefix='%s.__eq__' % self.sorts[attr.domain[p]],
                            domain=Bool,
                            args=OrderedDict([
                                ('lhs', TermMock(prefix='l' + p, domain=attr.domain[p])),
                                ('rhs', TermMock(prefix='r' + p, domain=attr.domain[p]))]))
                        for p in parameters
                    ]

                    return_value = operands.pop()
                    while operands:
                        return_value = TermMock(
                            prefix=Bool.__and__,
                            domain=Bool,
                            args=OrderedDict([('self', return_value), ('other', operands.pop())])
                        )

                    eq_axiom = make_eq_axiom(
                        lhs=TermMock(
                            prefix=attr,
                            domain=attr.codomain,
                            args=OrderedDict([
                                (p, TermMock(prefix='l' + p, domain=attr.domain[p]))
                                for p in parameters])),
                        rhs=TermMock(
                            prefix=attr,
                            domain=attr.codomain,
                            args=OrderedDict([
                                (p, TermMock(prefix='r' + p, domain=attr.domain[p]))
                                for p in parameters])),
                        sort=attr.codomain)
                    eq_axiom['return_value'] = return_value

                else:
                    eq_axiom = make_eq_axiom(
                        lhs=TermMock(prefix=attr, domain=attr.codomain),
                        rhs=TermMock(prefix=attr, domain=attr.codomain),
                        sort=attr.codomain)

                eqs.append(eq_axiom)

        l = TermMock(prefix='l', domain=sort)
        r = TermMock(prefix='r', domain=sort)

        ne_axiom = make_eq_axiom(lhs=l, rhs=r, sort=sort)
        ne_axiom['return_value'] = TermMock(
            prefix=Bool.__invert__,
            domain=Bool,
            args=OrderedDict([
                ('self', TermMock(
                    prefix='%s.__eq__' % sort.__name__,
                    domain=Bool,
                    args=OrderedDict([('lhs', l), ('rhs', r)])))])
        )

        self.axioms['%s.__eq__' % sort.__name__] = eqs
        self.axioms['%s.__ne__' % sort.__name__] = [ne_axiom]

    def dumps(self):
        for gen, name in self.generators.items():
            signature = inspect.signature(gen.fn).parameters
            signatures[slugify(name)] = (
                [nameof(gen.domain[p]) for p in signature],
                nameof(gen.codomain))

        for op, name in self.operations.items():
            signature = inspect.signature(op.fn).parameters
            signatures[slugify(name)] = (
                [nameof(op.domain[p]) for p in signature],
                nameof(op.codomain))

        for sort in self.sorts:
            if sort.__attributes__:
                for name in sort.__attributes__:
                    signatures[slugify('%s.__get_%s__' % (sort.__name__, name))] = (
                        [slugify(sort.__name__)],
                        slugify(getattr(sort, name).domain.__name__))

        variables = []
        for name in self.variables:
            variables += [(v['identifier'][1:], nameof(v['sort'])) for v in self.variables[name]]

        # import pprint
        # pprint.PrettyPrinter(indent=2).pprint(rewritten_axioms)
        # pprint.PrettyPrinter(indent=2).pprint(signatures)

        jinja_env = Environment(
            loader=FileSystemLoader(TEMPLATES_DIRECTORY),
            trim_blocks=True,
            lstrip_blocks=True)

        jinja_env.filters['slugify'] = slugify

        template = jinja_env.get_template('stratagem.ts')

        return template.render(
            adt=self.adt,
            sorts=self.sorts,
            signatures=signatures,
            variables=variables,
            axioms=rewritten_axioms)

    def make_variable(self, name, sort):
        if (name in self.variables):
            for variable in self.variables[name]:
                if sort == variable['sort']:
                    return variable['identifier']
        else:
            self.variables[name] = []

        variable = {'sort': sort, 'identifier': '$v%i' % self.next_variable_id}
        self.next_variable_id += 1
        self.variables[name].append(variable)
        return variable['identifier']

    def dump_term(self, term):
        if isinstance(term, str):
            print(term)
        if term.__args__:
            subterms = ', '.join(self.dump_term(subterm) for subterm in term.__args__.values())
            return self.nameof(term.__prefix__) + '(' + subterms + ')'

        if isinstance(term.__prefix__, generator):
            return self.nameof(term.__prefix__)
        return self.make_variable(term.__prefix__, term.__domain__)

    def nameof(self, prefix):
        if prefix in self.names:
            return self.names[prefix]

        if isinstance(prefix, generator):
            if isinstance(prefix, attr_constructor):
                self.names[prefix] = prefix.codomain.__name__ + '__constructor__'
                return self.names[prefix]

            qualname = prefix._fn.__qualname__.split('.')
            if qualname[0] == 'SortBase':
                qualname = [prefix._fn.__name__]
            if '<locals>' in qualname:
                del qualname[qualname.index('<locals>')]

            self.names[prefix] = '_'.join(qualname)
            return self.names[prefix]

        return prefix
