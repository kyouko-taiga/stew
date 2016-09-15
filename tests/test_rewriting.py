import unittest

from stew.core import Sort, Attribute, generator, operation
from stew.exceptions import MatchError, RewritingError
from stew.rewriting import Var, matches, if_, and_, or_, push_context


class S(Sort):

    @generator
    def nil() -> S: pass

    @generator
    def suc(self: S) -> S: pass


class T(Sort):

    @generator
    def cons(lhs: S, rhs: S) -> T: pass


class U(Sort):

    foo = Attribute(domain=S, default=S.nil())


class TestRewriting(unittest.TestCase):

    def test_pattern_matching(self):
        with push_context() as context:
            with S.nil().matches(S.nil()):
                self.assertTrue(context.writable)
            with S.suc(S.nil()).matches(S.suc(S.nil())):
                self.assertTrue(context.writable)

            with S.suc(S.nil()).matches(S.nil()):
                self.assertFalse(context.writable)

    def test_pattern_matching_on_multiple_terms(self):
        term_0 = S.nil()
        term_1 = S.suc(S.nil())

        with push_context() as context:
            with matches((term_0, term_0), (term_1, term_1)):
                self.assertTrue(context.writable)

            with matches((term_0, term_1), (term_1, term_1)):
                self.assertFalse(context.writable)
            with matches((term_0, term_0), (term_1, term_0)):
                self.assertFalse(context.writable)

    def test_pattern_matching_with_variables(self):
        # Test pattern matching on generators with single arguments.
        x = Var('x')

        with push_context() as context:
            term = S.suc(S.nil())
            with term.matches(x) as match:
                self.assertTrue(context.writable)
                self.assertIs(match.x, term)

            subterm = S.nil()
            with S.suc(subterm).matches(S.suc(x)) as match:
                self.assertTrue(context.writable)
                self.assertIs(match.x, subterm)

        # Test pattern matching on generators with multiple arguments.
        x = Var('x')
        y = Var('y')

        with push_context() as context:
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
        x = Var('x')

        with push_context() as context:
            subterm = S.suc(S.nil())
            with U(foo=subterm).matches(U(foo=x)) as match:
                self.assertTrue(context.writable)
                self.assertIs(match.x, subterm)

    def test_rewriting(self):

        @operation
        def f(x: S) -> S:
            yield x

        self.assertEqual(f(S.nil()), S.nil())
        self.assertEqual(f(S.suc(S.nil())), S.suc(S.nil()))

        @operation
        def f(x: S) -> S:
            if False:
                yield

        with self.assertRaises(RewritingError):
            f(S.nil())

    def test_rewriting_conditions(self):

        @operation
        def f(x: S) -> S:
            with if_(x != S.nil()):
                yield S.nil()
            yield S.suc(S.nil())

        self.assertEqual(f(S.suc(S.nil())), S.nil())
        self.assertEqual(f(S.nil()), S.suc(S.nil()))

    def test_rewriting_and_conditions(self):

        @operation
        def f(x: S, y: S) -> S:
            with if_(and_(x == S.nil(), y == S.nil())):
                yield S.nil()
            yield S.suc(S.nil())

        self.assertEqual(f(S.nil(), S.nil()), S.nil())
        self.assertEqual(f(S.nil(), S.suc(S.nil())), S.suc(S.nil()))
        self.assertEqual(f(S.suc(S.nil()), S.nil()), S.suc(S.nil()))
        self.assertEqual(f(S.suc(S.nil()), S.suc(S.nil())), S.suc(S.nil()))

    def test_rewriting_or_conditions(self):

        @operation
        def f(x: S, y: S) -> S:
            with if_(or_(x == S.nil(), y == S.nil())):
                yield S.nil()
            yield S.suc(S.nil())

        self.assertEqual(f(S.nil(), S.nil()), S.nil())
        self.assertEqual(f(S.nil(), S.suc(S.nil())), S.nil())
        self.assertEqual(f(S.suc(S.nil()), S.nil()), S.nil())
        self.assertEqual(f(S.suc(S.nil()), S.suc(S.nil())), S.suc(S.nil()))

    def test_rewriting_pattern_marching(self):

        @operation
        def f(x: S) -> S:
            v = Var('v')

            with x.matches(S.suc(v)):
                yield v
            yield x

        self.assertEqual(f(S.nil()), S.nil())
        self.assertEqual(f(S.suc(S.nil())), S.nil())
