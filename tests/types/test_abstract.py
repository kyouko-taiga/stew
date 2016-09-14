import unittest

from stew.core import Stew, Sort, generator
from stew.types.abstract import AbstractSort, create_abstract_sort


class TestSort(unittest.TestCase):

    def setUp(self):
        self.stew = Stew()

    def test_specialization(self):

        @self.stew.sort
        class S(Sort): pass

        @self.stew.sort
        class T(Sort): pass

        class Unspecialized(Sort):

            AbstractArg = create_abstract_sort()

            @generator
            def cons(arg: AbstractArg) -> Unspecialized: pass

        First = self.stew.specialize(Unspecialized, AbstractArg=S)
        Second = self.stew.specialize(Unspecialized, AbstractArg=T)

        self.assertIsInstance(Unspecialized.AbstractArg, AbstractSort)
        self.assertEqual(First.AbstractArg, S)
        self.assertEqual(Second.AbstractArg, T)

        self.assertTrue(issubclass(First, Unspecialized))
        self.assertTrue(issubclass(Second, Unspecialized))

        self.assertFalse(issubclass(First, Second))
        self.assertFalse(issubclass(Second, First))

    def test_default_specialization(self):

        @self.stew.sort
        class S(Sort): pass

        @self.stew.sort
        class T(Sort): pass

        class Unspecialized(Sort):

            AbstractArg = create_abstract_sort(default=S)

            @generator
            def cons(arg: AbstractArg) -> Unspecialized: pass

        First = self.stew.sort(Unspecialized)
        Second = self.stew.specialize(Unspecialized, AbstractArg=T)

        self.assertIsInstance(Unspecialized.AbstractArg, AbstractSort)
        self.assertEqual(First.AbstractArg, S)
        self.assertEqual(Second.AbstractArg, T)

        self.assertTrue(issubclass(First, Unspecialized))
        self.assertTrue(issubclass(Second, Unspecialized))
