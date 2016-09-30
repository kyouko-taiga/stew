import inspect


from collections import OrderedDict
from functools import reduce

from jinja2 import Environment, FileSystemLoader

from ..core import operation, generator
from ..settings import TEMPLATES_DIRECTORY
from ..types.bool import Bool

from .mocks import SortMock, TermMock
from .translator import Translator


true = TermMock(prefix=Bool.true)
false = TermMock(prefix=Bool.false)


def slugify(name):
    return name.replace('.', '_')


class StratagemTranslator(Translator):

    def __init__(self, adt=None):
        super().__init__()

        self.adt = adt or 'stew'

        self.variables = {}
        self.next_variable_id = 0

        self.register(Bool)

    def post_translate(self):
        for sort in self.sorts:
            self.register_eq_axioms(sort)

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
        nameof = lambda sort: slugify(sort.__name__)

        rewritten_axioms = []
        signatures = {}

        # Add the signature of the __eq__/__ne__ operations.
        boolname = slugify(Bool.__name__)
        for sort in self.sorts:
            sortname = slugify(sort.__name__)
            signatures[slugify('%s.__eq__' % sortname)] = ([sortname, sortname], boolname)
            signatures[slugify('%s.__ne__' % sortname)] = ([sortname, sortname], boolname)

        for axiom_name in self.axioms:
            # Collect all the guards associated with the axiom group.
            guards = reduce(
                lambda x, y: x + y, (axiom['guards'] for axiom in self.axioms[axiom_name]))

            if not guards:
                for axiom in self.axioms[axiom_name]:
                    rewritten_axioms.append({
                        'name': axiom_name,
                        'pattern': self.make_pattern(axiom['parameters'], axiom['matchs']),
                        'return_value': self.dump_term(axiom['return_value'])
                    })
                continue

            # Because strategem doesn't support guards on axioms, we have to
            # rewrite those that use guards so that they only rely on pattern
            # matching instead.
            guard_domains = [Bool for guard in guards]
            guard_params = [self.make_variable(i, sort) for i, sort in enumerate(guard_domains)]

            # Create (the signature of) a new operation whose domain is that
            # of the orginial one, plus a boolean for each guard that the
            # axioms of its semantics use.
            axiom_parameters = self.axioms[axiom_name][0]['parameters'].values()
            axiom_domain = self.axioms[axiom_name][0]['return_value'].__domain__
            signatures[slugify(axiom_name) + '_flat'] = (
                [nameof(d) for d in guard_domains] + [nameof(d) for d in axiom_parameters],
                nameof(axiom_domain))

            # Since concatenated all guards in one big list, we need to keep
            # track of the position of the first guard used by the axiom we're
            # considering to corretly set the pattern to match.
            guard_start = 0

            for axiom in self.axioms[axiom_name]:
                orig_left = self.make_pattern(axiom['parameters'], {})
                orig_right = [self.dump_term(false) for _ in range(len(guards))] + orig_left

                tran_left = list(guard_params)
                tran_left += self.make_pattern(axiom['parameters'], axiom['matchs'])

                for i, guard in enumerate(axiom['guards']):
                    term = self.dump_term(TermMock(
                        prefix='%s.%s' % (guard[0].__domain__.__name__, guard[1]),
                        domain=Bool,
                        args=OrderedDict([('left', guard[0]), ('right', guard[2])])
                    ))

                    guard_index = i + guard_start
                    orig_right[guard_index] = term
                    tran_left[guard_index] = term

                rewritten_axioms.append({
                    'name': axiom_name,
                    'pattern': orig_left,
                    'return_value': slugify(axiom_name) + '_flat(' + ', '.join(orig_right) + ')'
                })
                rewritten_axioms.append({
                    'name': axiom_name + '_flat',
                    'pattern': tran_left,
                    'return_value': self.dump_term(axiom['return_value'])
                })

                guard_start += len(axiom['guards'])

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

    def make_pattern(self, parameters, matchs):
        rv = []
        for name, sort in parameters.items():
            if name in matchs:
                rv.append(self.dump_term(matchs[name]))
            else:
                rv.append(self.make_variable(name, sort))
        return rv

    def dump_term(self, term):
        prefix = term.__prefix__
        if isinstance(prefix, operation):
            prefix = self.operations[prefix]
        elif isinstance(prefix, generator):
            prefix = self.generators[prefix]

        prefix = slugify(prefix)

        if term.__args__:
            subterms = ', '.join(self.dump_term(subterm) for subterm in term.__args__.values())
            return prefix + '(' + subterms + ')'

        if isinstance(term.__prefix__, generator):
            return prefix
        return self.make_variable(prefix, term.__domain__)
