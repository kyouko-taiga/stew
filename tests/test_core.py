import unittest

from stew.core import Stew, Sort
from stew.rewriting import Var


class TestSort(unittest.TestCase):

    def setUp(self):
        self.stew = Stew()

        @self.stew.sort
        class S(Sort):

            @self.stew.generator
            def nil() -> S: pass

            @self.stew.generator
            def suc(self: S) -> S: pass

    def test_generator_equality(self):
        S = self.stew.sorts['S']

        self.assertEqual(S.nil(), S.nil())
        self.assertEqual(S.suc(S.nil()), S.suc(S.nil()))
        self.assertEqual(S.suc(S.suc(S.nil())), S.suc(S.suc(S.nil())))
