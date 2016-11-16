from itertools import count
from functools import reduce
from operator import add

from jinja2 import Environment, FileSystemLoader

from ..core import Sort, generator, operation
from ..settings import TEMPLATES_DIRECTORY
from ..types.bool import Bool
from ..utils import make_generator, make_operation

from .terms import Term, is_linear, variables_of
from .translator import Translator


true = Term(prefix=Bool.true)
false = Term(prefix=Bool.false)


class Rule(object):

    def __init__(self, left, right):
        self.left = left
        self.right = right


class StratagemTranslator(Translator):

    def __init__(self, adt=None):
        super().__init__()

        self.adt = adt or 'stew'

        self.names = {}
        self.variables = {}
        self.next_variable_id = 0

        self.eqs = {}
        self.nes = {}

        self.copy_operations = {}
        self.copy_rules = []

        self.rules = {}
        self.flattened_signatures = {}

    @property
    def sort_generators(self):
        rv = {}
        for g in self.generators:
            try:
                rv[g.codomain].append(g)
            except KeyError:
                rv[g.codomain] = [g]
        return rv

    def pre_translate(self):
        self.register(Bool)
        self.register_cmp_operations()

    def post_translate(self):
        # Create basic rules from the translated axioms.
        self.make_basic_rules()

        # Linearize all rewriting rules.
        for operation in self.rules:
            linearized = []
            for rule in self.rules[operation]:
                linearized += self.linearize(rule)
            self.rules[operation] = linearized

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
        for op in self.axioms:
            self.rules[op] = self.make_basic_rule(op)

    def make_basic_rule(self, op):
        # Collect all the guards associated with the axiom group.
        guards = reduce(add, (axiom['guards'] for axiom in self.axioms[op]))

        rv = []

        # If the axioms don't use any guard, then we can translate
        # directly into basic rewriting rules.
        if not guards:
            for axiom in self.axioms[op]:
                rv.append(Rule(
                    left=Term(prefix=op, args=self.make_pattern(op, axiom)),
                    right=axiom['return_value']))
            return rv

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

        flattened_operation = make_operation(
            name=op._fn.__name__ + '_flat',
            domain=[('__guard%i' % i, Bool) for i in range(len(guards))] + list(op.domain.items()),
            codomain=op.codomain)
        self.operations.add(flattened_operation)

        guard_start = 0

        original = Rule(
            left=Term(
                prefix=op,
                args=[Term(prefix=p) for p in op.domain]),
            right=Term(
                prefix=flattened_operation,
                args=[false for _ in range(len(guards))] + [Term(prefix=p) for p in op.domain]))

        for axiom in self.axioms[op]:
            flattened = Rule(
                left=Term(
                    prefix=flattened_operation,
                    args=[
                        Term(prefix='__guard%i' % i) for i in range(len(guards))
                    ] + self.make_pattern(op, axiom)),
                right=axiom['return_value'])

            for i, guard in enumerate(axiom['guards']):
                comparison = (self.eqs if guard[1] == '__eq__' else self.nes)[guard[0].__domain__]
                term = Term(prefix=comparison, args=[guard[0], guard[2]])

                guard_name = '__guard%i' % (i + guard_start)
                flattened.left.__args__[guard_name] = true
                original.right.__args__[guard_name] = term

            rv.append(flattened)

            # Since we concatenated all guards in one big list, we have to
            # keep track of the position of the first guard used by the
            # axiom we're considering to corretly set the pattern to match.
            guard_start += len(axiom['guards'])

        rv.append(original)

        return rv

    def make_pattern(self, op, axiom):
        rv = []
        for name in op.domain:
            if name in axiom['matchs']:
                rv.append(axiom['matchs'][name])
            else:
                rv.append(Term(prefix=name))
        return rv

    def linearize(self, rule, side='left'):
        if is_linear(getattr(rule, side)):
            if side == 'left':
                return self.linearize(rule, side='right')
            return [rule]

        # Identify which subterms should be substitued to linearize the terms.
        term_variables = variables_of(getattr(rule, side))
        occurences = {}
        sorts = {}
        for var in term_variables:
            occurences[var.__prefix__] = occurences.get(var.__prefix__, 0) + 1
            sorts[var.__prefix__] = var.__domain__
        to_replace = [prefix for prefix in occurences if occurences[prefix] > 1]

        to_linearize = [rule]
        linearized = []

        for prefix in to_replace:
            for nonlinear_rule in to_linearize:
                for g in self.sort_generators[sorts[prefix]]:
                    # If the generator represents a constant (i.e. its domain
                    # is empty), we can simply substitute every occurence of
                    # non-linear variables with it.
                    if not g.domain:
                        substitution = Term(prefix=g, domain=g.codomain)
                        linearized.append(Rule(
                            self.substitute(prefix, nonlinear_rule.left, substitution),
                            self.substitute(prefix, nonlinear_rule.right, substitution)))

                    # However, the linearization of left and right terms isn't
                    # the same when the generator doesn't represent a constant.
                    elif side == 'left':
                        linearized.append(self.linearize_left_recursive(nonlinear_rule, prefix, g))
                    else:
                        linearized += self.linearize_right_recursive(
                            nonlinear_rule, prefix, g, occurences[prefix])

            to_linearize = linearized
            linearized = []

        # Linearize the transformed rules, as the linearization process might
        # have produced non-linear subterms.
        rv = to_linearize
        if side == 'left':
            rv = reduce(add, (self.linearize(new_rule, side='right') for new_rule in rv))
        return reduce(add, (self.linearize(new_rule, side='left') for new_rule in rv))

    def linearize_left_recursive(self, rule, prefix, g):

        # To linearize rules with recursive generators on their left, we have
        # to create a recursive rule whose left non-linear variables are
        # substitued with their constructor, using different names for each
        # argument whose sort is the generator codomain.

        # More formally, let g: (S, T0, ..., Tn) -> S be a generator of S, and
        # f: S, S, U0, ..., Um -> V an operation.
        # f(s, s, u0, ..., un) = v is transformed as
        # f(g(s0, t0, ..., tn), g(s1, t0, ..., tn), u0, ..., um) =
        # f(s0, s1, u0, ..., um).

        def pre():
            for i in count():
                yield Term(
                    prefix=g,
                    args=[
                        Term(prefix='__%i' % i if g.domain[p] == g.codomain else p)
                        for p in g.domain
                    ])

        def post():
            for i in count():
                yield Term(prefix='__%i' % i)

        return Rule(
            self.substitute(prefix, rule.left, pre(), using_generator=True),
            self.substitute(prefix, rule.left, post(), using_generator=True))

    def linearize_right_recursive(self, rule, prefix, g, n):

        # To linearize rules with recursive generators on their right, we have
        # to first duplicate non-linear variables as many times as they appear
        # in the term, to then feed them as the arguments of a new operation
        # that will rename them in the original term.

        # More formally, let g: (S, T0, ..., Tn) -> S be a generator of S, and
        # f: (S, U0, ..., Um) -> V an operation.
        # f(s, u0, ..., um) = h(s, s, u0, ..., um) is transformed as
        # f(s, u0, ..., um) = f'(copy(s), u0, ..., um) with
        # f'((s0, s1), u0, ..., um) = h(s0, s1, u0, ..., um).

        self.make_copy_rules(g.codomain, n)
        copy = self.copy_operations[g.codomain][n]

        non_recursive_args = [a for a in rule.left.__args__.values() if a.__prefix__ != prefix]
        prime = make_operation(
            name='prime',
            domain=[('__val', copy.codomain)] + [
                ('__%i' % i, a.__domain__)
                for i, a in enumerate(non_recursive_args)
            ],
            codomain=rule.right.__domain__)
        self.operations.add(prime)

        to_prime_right = Term(
            prefix=prime,
            args=[Term(prefix=copy, args=[Term(prefix=prefix)])] + non_recursive_args)

        def position(prefix, term, vector):
            if term.__prefix__ == prefix:
                return vector

            for i, subterm in enumerate(term.__args__.values()):
                subterm_position = position(prefix, subterm, vector + [i])
                if subterm_position is not None:
                    return subterm_position
            return None

        variable_prefix = ''.join(map(str, position(prefix, rule.right, [])))

        from_prime_left = Term(
            prefix=prime,
            args=[
                Term(
                    prefix=copy.codomain.tuple_generator,
                    args=[Term(prefix='__%s%i' % (variable_prefix, i)) for i in range(n)])
            ] + non_recursive_args)

        def post():
            for i in count():
                yield Term(prefix='__%s%i' % (variable_prefix, i))

        from_prime_right = self.substitute(prefix, rule.right, post(), using_generator=True)

        rv = [Rule(rule.left, to_prime_right), Rule(from_prime_left, from_prime_right)]
        return rv

    def make_copy_rules(self, sort, n=2):
        try:
            if n in self.copy_operations[sort]:
                return
        except KeyError:
            self.copy_operations[sort] = {}

        # Create a new sort to represent n-tuples of the given sort.
        sort_tuple = type(sort.__name__ + 'Tuple' + str(n), (Sort,), {})
        self.sorts.add(sort_tuple)

        # Create a generator for the tuple sort.
        tuple_generator = make_generator(
            'tuple', [('__%i' % i, sort) for i in range(n)], sort_tuple)
        self.generators.add(tuple_generator)
        sort_tuple.tuple_generator = tuple_generator

        # Create the copy operation.
        @operation
        def copy(__val: sort) -> sort_tuple:
            pass

        self.operations.add(copy)
        self.copy_operations[sort][n] = copy

        # Create the copy rules.
        for g in self.sort_generators[sort]:
            # If the domain of the generator is empty (i.e. it represents a
            # constant), we ca simply copy it `n` times in a tuple to form the
            # right term of the rule.
            if not g.domain:
                constant = Term(prefix=g)
                self.copy_rules.append(Rule(
                    Term(prefix=copy, args=[constant]),
                    Term(prefix=tuple_generator, args=[constant for _ in range(n)])))

            # If the domain of the generator isn't empty, we should create
            # an "expansion" operation that will apply the generator on `n`
            # copies of each of the generator's parameters.
            else:
                @operation
                def expand(__val: sort_tuple) -> sort_tuple:
                    pass

                self.operations.add(expand)

                # The copy rule should match the application of the generator
                # on `(x0, ..., xm)`, where `m` is the number of parameters it
                # takes.
                copy_left = Term(
                    prefix=copy,
                    args=[
                        Term(
                            prefix=g,
                            args=[Term(prefix='__%i' % i) for i in range(len(g.domain))])
                    ])

                # The right term of the copy rule is the application of the
                # expansion operation the application of the copy operation on
                # each parameter of the generator.
                copy_right = Term(
                    prefix=expand,
                    args=[
                        Term(
                            prefix=self.copy_operations[g.domain[p]][n],
                            args=[Term(prefix='__%i' % i) for i in range(len(g.domain))])
                        for p in g.domain
                    ])

                # The expansion operation should match `m` tuples of the form
                # `(pm0, ..., pmn)` where `pm` is the name of the mth
                # parameter of the generator.
                expand_left = Term(
                    prefix=expand,
                    args=[
                        Term(
                            prefix=tuple_generator,
                            args=[Term(prefix=p + str(i)) for i in range(n)])
                        for p in g.domain
                    ])

                # The right term of the expansion rule is a tuple consisting
                # of `n` applications of the generator on the copies of its
                # parameters.
                expand_right = Term(
                    prefix=tuple_generator,
                    args=[Term(
                        prefix=g,
                        args=[Term(prefix=p + str(i)) for p in g.domain])
                    for i in range(n)
                ])

                self.copy_rules.append(Rule(copy_left, copy_right))
                self.copy_rules.append(Rule(expand_left, expand_right))

    def substitute(self, prefix, term, substitution, using_generator=False):
        if term.__prefix__ == prefix:
            return next(substitution) if using_generator else substitution

        return Term(
            prefix=term.__prefix__,
            domain=term.__domain__,
            args=[
                self.substitute(prefix, subterm, substitution, using_generator)
                for subterm in term.__args__.values()])

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

    def nameof(self, prefix):
        if prefix in self.names:
            return self.names[prefix]

        if isinstance(prefix, type) and issubclass(prefix, Sort):
            self.names[prefix] = prefix.__name__ #+ hex(id(prefix))[-4:]#[2:]
        elif isinstance(prefix, generator):
            self.names[prefix] = prefix._fn.__name__ #+ hex(id(prefix))[-4:]#[2:]
        else:
            self.names[prefix] = prefix

        return self.names[prefix]

    def dumps(self):
        signatures = {}
        for obj in self.generators | self.operations:
            signatures[self.nameof(obj)] = (
                [self.nameof(d) for d in obj.domain.values()], self.nameof(obj.codomain))
        signatures.update(self.flattened_signatures)

        rules = {}
        for operation in self.rules:
            rules[operation] = [
                {'left': self.dump_term(rule.left), 'right': self.dump_term(rule.right)}
                for rule in self.rules[operation]
            ]
        rules['__copy_operations__'] = [
            {'left': self.dump_term(rule.left), 'right': self.dump_term(rule.right)}
            for rule in self.copy_rules
        ]

        variables = []
        for name in self.variables:
            variables += [(v['identifier'][1:], self.nameof(v['sort'])) for v in self.variables[name]]

        jinja_env = Environment(
            loader=FileSystemLoader(TEMPLATES_DIRECTORY),
            trim_blocks=True,
            lstrip_blocks=True)
        jinja_env.filters['nameof'] = self.nameof

        template = jinja_env.get_template('stratagem.ts')

        return template.render(
            adt=self.adt,
            sorts=self.sorts,
            signatures=signatures,
            variables=variables,
            rules=rules)

    def dump_term(self, term):
        if term.__args__:
            subterms = ', '.join(self.dump_term(subterm) for subterm in term.__args__.values())
            return self.nameof(term.__prefix__) + '(' + subterms + ')'

        if isinstance(term.__prefix__, generator):
            return self.nameof(term.__prefix__)
        return self.make_variable(term.__prefix__, term.__domain__)
