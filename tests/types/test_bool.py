import unittest

from stew.types.bool import Bool


class TestSort(unittest.TestCase):

    def test_generators(self):
        self.assertIs(Bool.true()._generator, Bool.true)
        self.assertIs(Bool.false()._generator, Bool.false)

    def test_invert(self):
        true = Bool.true()
        false = Bool.false()

        self.assertEqual(~true, false)
        self.assertEqual(~false, true)

    def test_and(self):
        true = Bool.true()
        false = Bool.false()

        self.assertEqual(true & true, true)
        self.assertEqual(true & false, false)
        self.assertEqual(false & true, false)
        self.assertEqual(false & false, false)

    def test_or(self):
        true = Bool.true()
        false = Bool.false()

        self.assertEqual(true | true, true)
        self.assertEqual(true | false, true)
        self.assertEqual(false | true, true)
        self.assertEqual(false | false, false)

    def test_xor(self):
        true = Bool.true()
        false = Bool.false()

        self.assertEqual(true ^ true, false)
        self.assertEqual(true ^ false, true)
        self.assertEqual(false ^ true, true)
        self.assertEqual(false ^ false, false)
