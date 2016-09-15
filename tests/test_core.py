import unittest

from stew.core import Sort, generator


class S(Sort):

    @generator
    def nil() -> S: pass

    @generator
    def suc(self: S) -> S: pass


class TestSort(unittest.TestCase):

    def test_generator_equality(self):
        self.assertEqual(S.nil(), S.nil())
        self.assertEqual(S.suc(S.nil()), S.suc(S.nil()))
        self.assertEqual(S.suc(S.suc(S.nil())), S.suc(S.suc(S.nil())))
