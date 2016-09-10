from ..core import Sort
from ..rewriting import Var


def make_nat_sort(stew):
    @stew.sort
    class Nat(Sort):
        @stew.generator
        def zero() -> Nat: pass

        @stew.generator
        def suc(self: Nat) -> Nat: pass

        @stew.operation
        def __add__(self: Nat, other: Nat) -> Nat:
            x = Var(name='x', domain=Nat)

            with self.matches(Nat.zero()):
                yield other
            with self.matches(Nat.suc(x)) as match:
                yield Nat.suc(match.x + other)

    return Nat
