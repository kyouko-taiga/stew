import unittest

from stew.core import Sort, generator
from stew.types.abstract import AbstractSort


class TestSort(unittest.TestCase):

    def test_specialization(self):

        class S(Sort):
            pass

        class T(Sort):
            pass

        class Unspecialized(Sort):

            AbstractArg = AbstractSort()

            @generator
            def cons(arg: AbstractArg) -> Unspecialized: pass

        First = Unspecialized.specialize(AbstractArg=S)
        Second = Unspecialized.specialize(AbstractArg=T)

        self.assertIsInstance(Unspecialized.AbstractArg, AbstractSort)
        self.assertEqual(First.AbstractArg, S)
        self.assertEqual(Second.AbstractArg, T)

        self.assertTrue(issubclass(First, Unspecialized))
        self.assertTrue(issubclass(Second, Unspecialized))

        self.assertFalse(issubclass(First, Second))
        self.assertFalse(issubclass(Second, First))
