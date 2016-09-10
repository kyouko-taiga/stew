import unittest

from stew.core import Stew, Sort
from stew.rewriting import Var


class TestRewriting(unittest.TestCase):

    def setUp(self):
        self.stew = Stew()

        @self.stew.sort
        class S(Sort):

            @self.stew.generator
            def nil() -> S: pass

            @self.stew.generator
            def suc(self: S) -> S: pass

    def test_pattern_matching(self):
        S = self.stew.sorts['S']

        with self.stew.rewriting_context:
            with S.nil().matches(S.nil()):
                self.assertTrue(self.stew._rewriting_context.writable)
            with S.suc(S.nil()).matches(S.suc(S.nil())):
                self.assertTrue(self.stew._rewriting_context.writable)

            with S.suc(S.nil()).matches(S.nil()):
                self.assertFalse(self.stew._rewriting_context.writable)

    def test_pattern_matching_with_variables(self):
        S = self.stew.sorts['S']
        x = Var(name='x', domain=S)

        with self.stew.rewriting_context:
            term = S.suc(S.nil())
            with term.matches(x) as match:
                self.assertTrue(self.stew._rewriting_context.writable)
                self.assertIs(match.x, term)

            subterm = S.nil()
            term = S.suc(subterm)
            with term.matches(S.suc(x)) as match:
                self.assertTrue(self.stew._rewriting_context.writable)
                self.assertIs(match.x, subterm)
