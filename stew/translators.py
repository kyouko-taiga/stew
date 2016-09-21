import ast
import astunparse
import inspect

from collections import OrderedDict
from functools import partial

from .core import Sort, generator, operation
from .exceptions import TranslationError
from .termtree import TermTree, TermTreeManager, make_term_from_call

from .types.bool import Bool


class Translator(object):

    def __init__(self):
        self.sorts = {}
        self.generators = {}
        self.operations = {}

    def register(self, obj, name=None):
        if isinstance(obj, type) and issubclass(obj, Sort):
            name = name or obj.__qualname__
            if obj in self.sorts:
                return name
            self.sorts[obj] = name

            # Register the generators and operations.
            for attr_name, attr_value in obj.__dict__.items():
                if isinstance(attr_value, (generator, operation)):
                    self.register(attr_value, name + '.' + attr_name)

        elif isinstance(obj, (generator, operation)):
            collection = self.operations if isinstance(obj, operation) else self.generators
            name = name or obj.__name__
            if obj in collection:
                return name
            collection[obj] = name

            # Register the sorts of the domain and codomain.
            for dependency in obj.domain.values():
                self.register(dependency)
            self.register(obj.codomain)

        else:
            raise TranslationError(
                "'%s' should be a sort, a generator, an operation or a strategy." % obj)

    def translate(self):
        rewriting_rules = []

        for operation in self.operations:
            # Parse the semantics of the operation.
            node = ast.parse(_unindent(inspect.getsource(operation.fn._original)))
            parser = _OperationParser(translator=self, operation=operation)
            parser.visit(node)

    def write_rule(self, operation, guard_parts, match_parts, return_value):
        guards = []
        for left, op, right in guard_parts:
            op = '==' if op == '__eq__' else '!='
            guards.append('(%s %s %s)' % (self.write_term(left), op, self.write_term(right)))
        guard = ' and '.join(guards)

        match = self.operations[operation] + '('
        for parameter in inspect.signature(operation.fn).parameters:
            if parameter in match_parts:
                match += self.write_term(match_parts[parameter]) + ', '
            else:
                match += parameter + ', '
        match = match.rstrip(', ') + ')'

        rule = (guard + ' => ' if guard else '') + match + ' = ' + self.write_term(return_value)
        print(rule)

    def write_term(self, term):
        term_name = term.name
        if isinstance(term_name, operation):
            term_name = self.operations[term_name]
        elif isinstance(term_name, generator):
            term_name = self.generators[term_name]

        if term.args:
            subterms = ', '.join(self.write_term(subterm) for subterm in term.args.values())
            return term_name+ '(' + subterms + ')'

        return term_name


class _OperationParser(ast.NodeVisitor):

    comparison_operators = {
        ast.Eq: '__eq__',
        ast.NotEq: '__ne__',
        ast.Lt: '__lt__',
        ast.LtE: '__le__',
        ast.GtE: '__ge__',
        ast.Gt: '__gt__',
        ast.In: '__contains__'
    }

    def __init__(self, translator, operation, stack=None):
        self.translator = translator
        self.operation = operation
        self.stack = stack or []

    @property
    def fn_scope(self):
        rv = dict(self.operation.fn._original.__globals__)
        rv.update(self.operation.fn._nonlocals)

        # Replace the sorts in the function scope with term generators.
        for name in rv:
            if isinstance(rv[name], type) and issubclass(rv[name], Sort) and (rv[name] != Sort):
                rv[name] = SortMock(rv[name])

        return rv

    def _dnf(self, node):
        if type(node) != ast.BoolOp:
            return node

        values = [self._dnf(child) for child in node.values]

        if type(node.op) == ast.Or:
            return ast.BoolOp(op=ast.Or(), values=values)

        for index, value in enumerate(values):
            if (type(value) == ast.BoolOp) and (type(value.op) == ast.Or):
                maxterm = values[index]
                values = values[:index] + values[index + 1:]
                values = [ast.BoolOp(op=ast.And(), values=[v] + values) for v in maxterm.values]
                return self._dnf(ast.BoolOp(op=ast.Or(), values=values))

        return node

    def visit_If(self, node):
        # If the test a boolean operation, we have to visit the then block for
        # each disjunction of the test.
        if type(node.test) == ast.BoolOp:
            test = self._dnf(node.test)

            if type(test.op) == ast.Or:
                for value in test.values:
                    thenparser = self._make_subparser(self.stack + [value])
                    for child in node.body:
                        thenparser.visit(child)

            if type(test.op) == ast.And:
                thenparser = self._make_subparser(self.stack + test.values)
                for child in node.body:
                    thenparser.visit(child)

        # Otherwise, we can visit the then block directly.
        else:
            thenparser = self._make_subparser(self.stack + [node.test])
            for child in node.body:
                thenparser.visit(child)

        # Visit the else block.
        for child in node.orelse:
            self.visit(child)

    def visit_Return(self, node):
        # Create a variable manager here so that we can keep track of the
        # domain of the variables while parsing the rule.
        var_manager = TermTreeManager()

        # Parse the rule conditions and return value.
        (guard_parts, match_parts) = self.parse_conditions(var_manager)
        return_value = self.parse_expr(node.value, var_manager)

        # Call the translator to rewrite the parsed rule.
        self.translator.write_rule(self.operation, guard_parts, match_parts, return_value)

    def parse_conditions(self, var_manager):
        guard_parts = []
        match_parts = {}

        for condition in self.stack:
            (guard_part, match_part) = self.parse_condition(condition, var_manager)
            if guard_part is not None:
                guard_parts.append(guard_part)
            if match_part is not None:
                match_parts.update({match_part[0]: match_part[1]})

        return (guard_parts, match_parts)

    def parse_condition(self, node, var_manager):
        """
        Returns a tuple `(guard_part, match_part)`.

        `guard_part` is either `None` if the condition should be translated
        as the guard part of the rule, or a tuple `(left, op, right)` where
        `left` and`right` are the operands and `op` is the name of the
        comparison operator.

        `match_part` is either `None` if the condition should be translated
        as the matching part of the rule, or a tuple `(left, right)` where
        `right` is the pattern `left` should match.
        """

        if type(node) == ast.Compare:
            # In Python, it is possible to compare more than two values in a
            # single "comparison" (e.g. 1 < x < 9), but we forbid this syntax
            # here in favor of (1 < x) and (x < 9) which arguably has a
            # clearer semantics.
            if len(node.ops) > 1:
                raise TranslationError('Comparison of more than two values might be ambiguous.')

            left = self.parse_expr(node.left, var_manager)
            right = self.parse_expr(node.comparators[0], var_manager)

            # TODO Make sure left and right aren't both variables.

            # If the operator is __eq__ and one of the operand is a parameter
            # of the operation, we should translate this condition as a part
            # of the the matching side of the rule.
            if type(node.ops[0]) == ast.Eq:
                # Since pattern matching can only be used with __eq__, if one
                # of the operands is a variable, we can infer its type from
                # that of the other one.
                if left.domain is None:
                    left.domain = right.domain
                elif right.domain is None:
                    right.domain = left.domain

                if left.name in self.operation.domain:
                    return (None, (left.name, right))
                elif right.name in self.operation.domain:
                    return (None, (right.name, left))

            operator_name = self.comparison_operators[type(node.ops[0])]

            # If the operator is either __eq__ or __ne__, between operands
            # that aren't parameter of the operation, we can assume the
            # condition should be translated as a guard of the rule.
            if operator_name in ('__eq__', '__ne__'):
                return ((left, operator_name, right), None)

            # For any other operator, we have to check if the result of the
            # expression evaluates as a built-in bool and create an __eq__
            # guard if it does.
            operation = getattr(left.domain, operator_name)
            if not issubclass(operation.codomain, Bool):
                raise TranslationError(
                    'Cannot implicitly convert %s to a condition. '
                    'Use "==" or "!=" to create explicit conditions.')

            parameters = inspect.signature(operation.fn).parameters
            term_args = OrderedDict([
                (parameter, value) for parameter, value in zip(parameters, (left, right))])

            left = TermTree(name=operation, domain=operation.codomain, args=term_args)
            right = getattr(SortMock(operation.codomain), 'true')()
            return ((left, '__eq__', right), None)

    def parse_expr(self, node, var_manager):
        if type(node) == ast.Name:
            # If the node refers to a parameter of the operation, we simply
            # its name.
            if node.id in self.operation.domain:
                return TermTree(name=node.id, domain=self.operation.domain[node.id])

            # If the node refers to a python object, we retrieve it from the
            # scope of the operation and parse it.
            return self.parse_object(self.fn_scope[node.id])

        else:
            # If the node refers to an arbitrary expression, we evaluate it as
            # a python object and parse it.
            src = astunparse.unparse(node)

            scope = dict(self.fn_scope)
            scope['var'] = var_manager

            # Inject the arguments of the function.
            local_vars = {}
            for name in self.operation.domain:
                local_vars[name] = getattr(var_manager, name)
                local_vars[name].domain = self.operation.domain[name]

            obj = eval(src, scope, local_vars)

            return self.parse_object(obj)

    def parse_object(self, obj):
        if isinstance(obj, TermTree):
            return obj

        # if isinstance(obj, Sort):
        #     term_name = None
        #     named_args = {}
        #
        #     # If the object is a generator, we lookup its name in the
        #     # registered generators and we parse its arguments.
        #     if obj._is_a_constant:
        #         term_name = self.translator.generators[obj._generator]
        #         if obj._generator_args is not None:
        #             named_args.update({
        #                 name: self.parse_object(value)
        #                 for name, value in obj._generator_args.items()})
        #
        #     # If the object is a record, we lookup its name in the registered
        #     # sorts and we parse its attributes.
        #     else:
        #         term_name = self.translator.sorts[obj.__class__]
        #         named_args.update({
        #             name: self.parse_object(getattr(obj, name))
        #             for name in obj.__attributes__})
        #
        #     return TermTree(term_name, named_args=named_args)

        # If the given python object isn't an instance of a sort, we can't
        # parse it as a term.
        raise TranslationError('Cannot parse %s.' % obj)

    def _make_subparser(self, stack):
        return _OperationParser(translator=self.translator, operation=self.operation, stack = stack)


class SortMock(object):

    def __init__(self, target):
        self.target = target

    def __getattr__(self, name):
        attr = getattr(self.target, name)
        if isinstance(attr, (generator, operation)):
            # Create a function that generates the term corresponding to a
            # call to the accessed generator or operation.
            return partial(make_term_from_call, attr)

        # TODO Handle attributes.

        raise TranslationError(
            'Cannot translate %s because it is not a generator, an operation nor an attribute.')


def _unindent(src):
    indentation = len(src) - len(src.lstrip())
    return '\n'.join([line[indentation:] for line in src.split('\n')])
