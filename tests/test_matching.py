import unittest

from stew.core import Sort, Attribute, generator, operation
from stew.exceptions import MatchError, RewritingError
from stew.matching import push_context, var


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

        with push_context():
            self.assertEqual(S.nil(), S.nil())
        with push_context():
            self.assertEqual(S.suc(S.nil()), S.suc(S.nil()))

        with push_context():
            self.assertNotEqual(S.nil(), S.suc(S.nil()))

    def test_pattern_matching_on_multiple_terms(self):
        term_0 = S.nil()
        term_1 = S.suc(S.nil())

        with push_context():
            self.assertTrue((term_0 == term_0) and (term_1 == term_1))

        with push_context():
            self.assertFalse((term_0 == term_1) and (term_1 == term_1))
        with push_context():
            self.assertFalse((term_0 == term_0) and (term_1 == term_0))

    def test_pattern_matching_with_variables(self):
        with push_context() as context:
            term = S.suc(S.nil())

            self.assertEqual(term, var.x)
            self.assertIs(var.x, term)

        with push_context() as context:
            subterm = S.nil()

            self.assertEqual(S.suc(subterm), S.suc(var.x))
            self.assertIs(var.x, subterm)

        with push_context() as context:
            lhs = S.nil()
            rhs = S.suc(S.nil())

            self.assertEqual(T.cons(lhs=lhs, rhs=rhs), T.cons(lhs=var.x, rhs=var.y))
            self.assertIs(var.x, lhs)
            self.assertIs(var.y, rhs)

        with push_context() as context:
            lhs = S.nil()
            rhs = S.nil()

            self.assertEqual(T.cons(lhs=lhs, rhs=rhs), T.cons(lhs=var.x, rhs=var.x))
            self.assertEqual(var.x, lhs)

        with push_context() as context:
            lhs = S.nil()
            rhs = S.suc(S.nil())

            self.assertNotEqual(T.cons(lhs=lhs, rhs=rhs), T.cons(lhs=var.x, rhs=var.x))

        with push_context() as context:
            subterm = S.suc(S.nil())

            self.assertEqual(U(foo=subterm), U(foo=var.x))
            self.assertIs(var.x, subterm)

    def test_rewriting(self):

        @operation
        def f(x: S) -> S:
            return x

        self.assertEqual(f(S.nil()), S.nil())
        self.assertEqual(f(S.suc(S.nil())), S.suc(S.nil()))

        @operation
        def f(x: S) -> S:
            pass

        with self.assertRaises(RewritingError):
            f(S.nil())

    # def test_rewriting_and_conditions(self):
    #
    #     @operation
    #     def f(x: S, y: S) -> S:
    #         with if_(and_(x == S.nil(), y == S.nil())):
    #             yield S.nil()
    #         yield S.suc(S.nil())
    #
    #     self.assertEqual(f(S.nil(), S.nil()), S.nil())
    #     self.assertEqual(f(S.nil(), S.suc(S.nil())), S.suc(S.nil()))
    #     self.assertEqual(f(S.suc(S.nil()), S.nil()), S.suc(S.nil()))
    #     self.assertEqual(f(S.suc(S.nil()), S.suc(S.nil())), S.suc(S.nil()))
    #
    # def test_rewriting_or_conditions(self):
    #
    #     @operation
    #     def f(x: S, y: S) -> S:
    #         with if_(or_(x == S.nil(), y == S.nil())):
    #             yield S.nil()
    #         yield S.suc(S.nil())
    #
    #     self.assertEqual(f(S.nil(), S.nil()), S.nil())
    #     self.assertEqual(f(S.nil(), S.suc(S.nil())), S.nil())
    #     self.assertEqual(f(S.suc(S.nil()), S.nil()), S.nil())
    #     self.assertEqual(f(S.suc(S.nil()), S.suc(S.nil())), S.suc(S.nil()))

    def test_rewriting_pattern_marching(self):

        @operation
        def f(x: S) -> S:
            if x == S.suc(var.v):
                return var.v
            return x

        self.assertEqual(f(S.nil()), S.nil())
        self.assertEqual(f(S.suc(S.nil())), S.nil())
