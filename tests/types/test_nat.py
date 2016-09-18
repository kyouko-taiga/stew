import unittest

from stew.exceptions import ArgumentError, RewritingError
from stew.types.bool import Bool
from stew.types.nat import Nat


class TestSort(unittest.TestCase):

    def test_generators(self):
        self.assertIs(Nat.zero()._generator, Nat.zero)
        self.assertIs(Nat.suc(Nat.zero())._generator, Nat.suc)

    def test_constructor_helper(self):
        self.assertEqual(Nat(0), Nat.zero())
        self.assertEqual(Nat(1), Nat.suc(Nat.zero()))
        self.assertEqual(Nat(2), Nat.suc(Nat.suc(Nat.zero())))

        with self.assertRaises(ArgumentError):
            Nat(-1)

    def test_add(self):
        self.assertEqual(Nat(0) + Nat(0), Nat(0))
        self.assertEqual(Nat(0) + Nat(2), Nat(2))
        self.assertEqual(Nat(2) + Nat(0), Nat(2))
        self.assertEqual(Nat(2) + Nat(2), Nat(4))

    def test_sub(self):
        self.assertEqual(Nat(0) - Nat(0), Nat(0))
        self.assertEqual(Nat(2) - Nat(0), Nat(2))
        self.assertEqual(Nat(2) - Nat(1), Nat(1))

        with self.assertRaises(RewritingError):
            Nat(2) - Nat(3)

    def test_mul(self):
        self.assertEqual(Nat(0) * Nat(2), Nat(0))
        self.assertEqual(Nat(2) * Nat(0), Nat(0))
        self.assertEqual(Nat(2) * Nat(3), Nat(6))
        self.assertEqual(Nat(3) * Nat(2), Nat(6))

    def test_truediv(self):
        self.assertEqual(Nat(0) / Nat(2), Nat(0))
        self.assertEqual(Nat(1) / Nat(2), Nat(0))
        self.assertEqual(Nat(2) / Nat(2), Nat(1))
        self.assertEqual(Nat(3) / Nat(2), Nat(1))
        self.assertEqual(Nat(4) / Nat(2), Nat(2))

        with self.assertRaises(RewritingError):
            Nat(2) / Nat(0)

    def test_mod(self):
        self.assertEqual(Nat(0) % Nat(2), Nat(0))
        self.assertEqual(Nat(1) % Nat(2), Nat(1))
        self.assertEqual(Nat(2) % Nat(2), Nat(0))
        self.assertEqual(Nat(3) % Nat(2), Nat(1))
        self.assertEqual(Nat(4) % Nat(2), Nat(0))

        with self.assertRaises(RewritingError):
            Nat(2) % Nat(0)

    def test_lt(self):
        self.assertEqual(Nat(1) < Nat(2), Bool.true())
        self.assertEqual(Nat(2) < Nat(2), Bool.false())
        self.assertEqual(Nat(3) < Nat(2), Bool.false())

    def test_le(self):
        self.assertEqual(Nat(1) <= Nat(2), Bool.true())
        self.assertEqual(Nat(2) <= Nat(2), Bool.true())
        self.assertEqual(Nat(3) <= Nat(2), Bool.false())

    def test_ge(self):
        self.assertEqual(Nat(1) >= Nat(2), Bool.false())
        self.assertEqual(Nat(2) >= Nat(2), Bool.true())
        self.assertEqual(Nat(3) >= Nat(2), Bool.true())

    def test_gt(self):
        self.assertEqual(Nat(1) > Nat(2), Bool.false())
        self.assertEqual(Nat(2) > Nat(2), Bool.false())
        self.assertEqual(Nat(3) > Nat(2), Bool.true())
