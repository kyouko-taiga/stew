import unittest

from stew.core import Stew, Sort, Attribute
from stew.exceptions import MatchError, RewritingError
from stew.rewriting import Var, and_, or_


class TestRewriting(unittest.TestCase):

    def setUp(self):
        self.stew = Stew()

        @self.stew.sort
        class S(Sort):

            @self.stew.generator
            def nil() -> S: pass

            @self.stew.generator
            def suc(self: S) -> S: pass

        @self.stew.sort
        class T(Sort):

            @self.stew.generator
            def cons(lhs: S, rhs: S) -> T: pass

        @self.stew.sort
        class U(Sort):

            foo = Attribute(domain=S, default=S.nil())

    def test_pattern_matching(self):
        S = self.stew.sorts['S']

        with self.stew.rewriting_context as context:
            with S.nil().matches(S.nil()):
                self.assertTrue(context.writable)
            with S.suc(S.nil()).matches(S.suc(S.nil())):
                self.assertTrue(context.writable)

            with S.suc(S.nil()).matches(S.nil()):
                self.assertFalse(context.writable)

    def test_pattern_matching_with_variables(self):
        # Test pattern matching on generators with single arguments.
        S = self.stew.sorts['S']
        x = Var(name='x', domain=S)

        with self.stew.rewriting_context as context:
            term = S.suc(S.nil())
            with term.matches(x) as match:
                self.assertTrue(context.writable)
                self.assertIs(match.x, term)

            subterm = S.nil()
            with S.suc(subterm).matches(S.suc(x)) as match:
                self.assertTrue(context.writable)
                self.assertIs(match.x, subterm)

        # Test pattern matching on generators with multiple arguments.
        T = self.stew.sorts['T']
        x = Var(name='x', domain=S)
        y = Var(name='y', domain=S)

        with self.stew.rewriting_context as context:
            lhs_subterm = S.nil()
            rhs_subterm = S.suc(S.nil())
            with T.cons(lhs=lhs_subterm, rhs=rhs_subterm).matches(T.cons(lhs=x, rhs=y)) as match:
                self.assertTrue(context.writable)
                self.assertIs(match.x, lhs_subterm)
                self.assertIs(match.y, rhs_subterm)

            lhs_subterm = S.nil()
            rhs_subterm = S.nil()
            with T.cons(lhs=lhs_subterm, rhs=rhs_subterm).matches(T.cons(lhs=x, rhs=x)) as match:
                self.assertTrue(context.writable)
                self.assertEqual(match.x, lhs_subterm)

            lhs_subterm = S.nil()
            rhs_subterm = S.suc(S.nil())
            with T.cons(lhs=lhs_subterm, rhs=rhs_subterm).matches(T.cons(lhs=x, rhs=x)) as match:
                self.assertFalse(context.writable)

        # Test pattern matching on sorts with attributes.
        U = self.stew.sorts['U']
        x = Var(name='x', domain=S)

        with self.stew.rewriting_context as context:
            subterm = S.suc(S.nil())
            with U(foo=subterm).matches(U(foo=x)) as match:
                self.assertTrue(context.writable)
                self.assertIs(match.x, subterm)

    def test_rewriting(self):
        S = self.stew.sorts['S']

        @self.stew.operation
        def f(x: S) -> S:
            yield x

        self.assertEqual(f(S.nil()), S.nil())
        self.assertEqual(f(S.suc(S.nil())), S.suc(S.nil()))

        @self.stew.operation
        def f(x: S) -> S:
            if False:
                yield

        with self.assertRaises(RewritingError):
            f(S.nil())

    def test_rewriting_conditions(self):
        S = self.stew.sorts['S']

        @self.stew.operation
        def f(x: S) -> S:
            with self.stew.if_(x != S.nil()):
                yield S.nil()
            yield S.suc(S.nil())

        self.assertEqual(f(S.suc(S.nil())), S.nil())
        self.assertEqual(f(S.nil()), S.suc(S.nil()))

    def test_rewriting_and_conditions(self):
        S = self.stew.sorts['S']

        @self.stew.operation
        def f(x: S, y: S) -> S:
            with self.stew.if_(and_(x == S.nil(), y == S.nil())):
                yield S.nil()
            yield S.suc(S.nil())

        self.assertEqual(f(S.nil(), S.nil()), S.nil())
        self.assertEqual(f(S.nil(), S.suc(S.nil())), S.suc(S.nil()))
        self.assertEqual(f(S.suc(S.nil()), S.nil()), S.suc(S.nil()))
        self.assertEqual(f(S.suc(S.nil()), S.suc(S.nil())), S.suc(S.nil()))

    def test_rewriting_or_conditions(self):
        S = self.stew.sorts['S']

        @self.stew.operation
        def f(x: S, y: S) -> S:
            with self.stew.if_(or_(x == S.nil(), y == S.nil())):
                yield S.nil()
            yield S.suc(S.nil())

        self.assertEqual(f(S.nil(), S.nil()), S.nil())
        self.assertEqual(f(S.nil(), S.suc(S.nil())), S.nil())
        self.assertEqual(f(S.suc(S.nil()), S.nil()), S.nil())
        self.assertEqual(f(S.suc(S.nil()), S.suc(S.nil())), S.suc(S.nil()))

    def test_rewriting_pattern_marching(self):
        S = self.stew.sorts['S']

        @self.stew.operation
        def f(x: S) -> S:
            v = Var(name='v', domain=S)

            with x.matches(S.suc(v)):
                yield v
            yield x

        self.assertEqual(f(S.nil()), S.nil())
        self.assertEqual(f(S.suc(S.nil())), S.nil())
