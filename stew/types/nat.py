from ..core import Sort, generator, operation
from ..exceptions import ArgumentError
from ..rewriting import Var


class Nat(Sort):

    def __init__(self, *args, **kwargs):
        if (len(args) == 1) and isinstance(args[0], int):
            number = args[0]

            Sort.__init__(self)
            if number == 0:
                self._generator = Nat.zero
            elif number > 0:
                self._generator = Nat.suc
                self._generator_args = {'self': Nat(number - 1)}
            else:
                raise ArgumentError(
                    'Cannot initialize %s with a negative number.' % self.__class__.__name__)

        else:
            Sort.__init__(self, **kwargs)

    @generator
    def zero() -> Nat: pass

    @generator
    def suc(self: Nat) -> Nat: pass

    @operation
    def __add__(self: Nat, other: Nat) -> Nat:
        x = Var('x')

        # zero + y = y
        with self.matches(Nat.zero()):
            yield other

        # suc(x) + y = suc(x + y)
        with self.matches(Nat.suc(x)) as match:
            yield Nat.suc(match.x + other)

    @operation
    def __sub__(self: Nat, other: Nat) -> Nat:
        x = Var('x')
        y = Var('y')

        # x - 0 = x
        with other.matches(Nat.zero()):
            yield self

        # suc(x) - suc(y) = x - y
        with self.stew.matches((self, Nat.suc(x)), (other, Nat.suc(y))) as match:
            yield match.x - match.y

    @operation
    def __mul__(self: Nat, other: Nat) -> Nat:
        x = Var('x')

        # 0 * y = 0
        with self.matches(Nat.zero()):
            yield Nat.zero()

        # suc(x) * y = x * y + y
        with self.matches(Nat.suc(x)) as match:
            yield match.x * other + other

    def _as_int(self):
        if self._generator == Nat.zero:
            return 0
        elif self._generator == Nat.suc:
            return 1 + self._generator_args['self']._as_int()

    def __str__(self):
        return '%s(%i)' % (self.__class__.__name__, self._as_int())
