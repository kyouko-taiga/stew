import ast
import astunparse
import inspect

from collections import OrderedDict

from ..core import Sort, generator, operation
from ..exceptions import TranslationError
from ..types.bool import Bool

from .mocks import TermMock, TermMockManager, SortMock, make_term_from_call


class Translator(object):

    def __init__(self):
        self.sorts = {}
        self.generators = {}
        self.operations = {}

        self.accessors = {}

    def register(self, obj, name=None):
        if isinstance(obj, type) and issubclass(obj, Sort):
            name = name or obj.__qualname__
            if obj in self.sorts:
                return name
            self.sorts[obj] = name

            # If the sort has attributes, create and register a generator that
            # accepts them and register accessors to extract them.
            if obj.__attributes__:
                # Generate the code definition of the function.
                fn_attributes = ', '.join(
                    '%s: %s' % (name, getattr(obj, name).domain.__name__)
                    for name in obj.__attributes__)
                src = 'def __init__(%s) -> %s: pass' % (fn_attributes, obj.__name__)

                # Create the scope of the code to evaluate.
                sorts = [getattr(obj, name).domain for name in obj.__attributes__] + [obj]
                scope = {sort.__name__: sort for sort in sorts}

                # Create and register the new generator.
                eval_locals = {}
                eval(compile(src, filename='<null>', mode='exec'), scope, eval_locals)

                gen = generator(eval_locals['__init__'])
                obj.__attr_constructor__ = gen
                self.register(gen, name + '.__init__')

                # Register the attribute accessors.
                for attribute_name in obj.__attributes__:
                    operation_name = '__get_%s__' % attribute_name
                    self.accessors[name + '.' + operation_name] = {
                        'parameters': ('term',),
                        'match_parts': {
                            'term': TermMock(
                                prefix=name + '.__init__',
                                domain=obj,
                                args=OrderedDict([
                                    (name, TermMock(prefix=name, domain=getattr(obj, name).domain))
                                    for name in obj.__attributes__]))
                        },
                        'return_value': TermMock(
                            prefix=attribute_name,
                            domain=getattr(obj, attribute_name).domain)
                    }

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
        for accessor_name, accessor in self.accessors.items():
            self.write_rule(
                name=accessor_name,
                parameters=accessor['parameters'],
                guard_parts=[],
                match_parts=accessor['match_parts'],
                return_value=accessor['return_value'])

        for operation in self.operations:
            # Parse the semantics of the operation.
            node = ast.parse(_unindent(inspect.getsource(operation.fn._original)))
            node = _TransformIfExpReturn().visit(node)
            parser = _OperationParser(translator=self, operation=operation)
            parser.visit(node)

    def write_rule(self, name, parameters, guard_parts, match_parts, return_value):
        raise NotImplementedError


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

    def __init__(self, translator, operation, stack=None, local_vars=None):
        self.translator = translator
        self.operation = operation
        self.stack = stack or []

        self.locals = local_vars or {}

    @property
    def fn_scope(self):
        rv = dict(self.operation.fn._original.__globals__)
        rv.update(self.operation.fn._nonlocals)

        # Replace the sorts in the function scope with term generators.
        for name in rv:
            if isinstance(rv[name], type) and issubclass(rv[name], Sort) and (rv[name] != Sort):
                rv[name] = SortMock(rv[name])

        return rv

    def visit_Assign(self, node):
        for target in node.targets:
            if type(target) == ast.Name:
                self.locals[target.id] = node.value
            elif type(target) == ast.Tuple:
                raise TranslationError('Cannot translate variable unpacking.')

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
        var_manager = TermMockManager()

        # Parse the rule conditions and return value.
        (guard_parts, match_parts) = self.parse_conditions(var_manager)
        return_value = self.parse_expr(node.value, var_manager)

        name = self.translator.operations[self.operation]
        parameters = inspect.signature(self.operation.fn).parameters

        # Call the translator to rewrite the parsed rule.
        self.translator.write_rule(name, parameters, guard_parts, match_parts, return_value)

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
                if left.__domain__ is None:
                    left.__domain__ = right.__domain__
                elif right.__domain__ is None:
                    right.__domain__ = left.__domain__

                if left.__prefix__ in self.operation.domain:
                    return (None, (left.__prefix__, right))
                elif right.__prefix__ in self.operation.domain:
                    return (None, (right.__prefix__, left))

            operator_name = self.comparison_operators[type(node.ops[0])]

            # If the operator is either __eq__ or __ne__, between operands
            # that aren't parameter of the operation, we can assume the
            # condition should be translated as a guard of the rule.
            if operator_name in ('__eq__', '__ne__'):
                return ((left, operator_name, right), None)

            # For any other operator, we have to check if the result of the
            # expression evaluates as a built-in bool and create an __eq__
            # guard if it does.
            operation = getattr(left.__domain__, operator_name)
            if not issubclass(operation.codomain, Bool):
                raise TranslationError(
                    'Cannot implicitly convert %s to a condition. '
                    'Use "==" or "!=" to create explicit conditions.')

            parameters = inspect.signature(operation.fn).parameters
            term_args = OrderedDict([
                (parameter, value) for parameter, value in zip(parameters, (left, right))])

            left = TermMock(prefix=operation, domain=operation.codomain, args=term_args)
            right = getattr(SortMock(operation.codomain), 'true')()
            return ((left, '__eq__', right), None)

    def parse_expr(self, node, var_manager):
        # Dereferences local variables.
        node = _Dereferencer(self.locals).visit(node)

        if type(node) == ast.Name:
            # If the node refers to a parameter of the operation, we simply
            # return a term representing its name.
            if node.id in self.operation.domain:
                return TermMock(prefix=node.id, domain=self.operation.domain[node.id])

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
                local_vars[name].__domain__ = self.operation.domain[name]

            obj = eval(src, scope, local_vars)

            return self.parse_object(obj)

    def parse_object(self, obj):
        if isinstance(obj, TermMock):
            return obj

        if isinstance(obj, Sort):
            # If the object is the result of a sort generator, we create a
            # term from its generator function and arguments.
            if obj._is_a_constant:
                if obj._generator_args is not None:
                    term_args = {
                        name: self.parse_object(value)
                        for name, value in obj._generator_args.items()}
                else:
                    term_args = {}

                return make_term_from_call(obj._generator, **term_args)

            # If the object is a record, we create a term from its constructor
            # argument and the value of its attributes.
            return TermMock(
                prefix=obj.__attr_constructor__,
                domain=obj.__class__,
                args=OrderedDict([(name, getattr(obj, name)) for name in obj.__attributes__]))

        # If the given python object isn't an instance of a sort, we can't
        # parse it as a term.
        raise TranslationError('Cannot parse %s.' % obj)

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

    def _make_subparser(self, stack):
        return _OperationParser(
            translator=self.translator,
            operation=self.operation,
            stack=stack,
            local_vars=self.locals)


class _Dereferencer(ast.NodeTransformer):

    def __init__(self, references):
        self.references = references

    def visit_Name(self, node):
        return self.references.get(node.id, node)


class _TransformIfExpReturn(ast.NodeTransformer):

    def visit_Return(self, node):
        if type(node.value) == ast.IfExp:
            return self.visit(ast.If(
                test=node.value.test,
                body=[ast.Return(value=node.value.body)],
                orelse=[ast.Return(value=node.value.orelse)]))
        return node


def _unindent(src):
    indentation = len(src) - len(src.lstrip())
    return '\n'.join([line[indentation:] for line in src.split('\n')])
