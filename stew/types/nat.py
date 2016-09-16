from ..core import Sort, generator, operation
from ..exceptions import ArgumentError
from ..matching import var

from .bool import Bool


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
        # zero + y = y
        if self == Nat.zero():
            return other

        # suc(x) + y = suc(x + y)
        if self == Nat.suc(var.x):
            return Nat.suc(var.x + other)

    @operation
    def __sub__(self: Nat, other: Nat) -> Nat:
        # x - 0 = x
        if other == Nat.zero():
            return self

        # suc(x) - suc(y) = x - y
        if self == Nat.suc(var.x) and other == Nat.suc(var.y):
            return var.x - var.y

    @operation
    def __mul__(self: Nat, other: Nat) -> Nat:
        # 0 * y = 0
        if self == Nat.zero():
            return Nat.zero()

        # suc(x) * y = x * y + y
        if self == Nat.suc(var.x):
            return var.x * other + other

    @operation
    def __truediv__(self: Nat, other: Nat) -> Nat:
        # if x < y then x / y = 0
        if self < other:
            return Nat.zero()

        # if (x >= y) and (y != 0) then x / y = suc((x - y) / y)
        if (self >= other) and (other != Nat.zero()):
            return Nat.suc((self - other) / other)

    @operation
    def __mod__(self: Nat, other: Nat) -> Nat:
        # if y != 0 then x % y = x - (y * (x / y))
        if other != Nat.zero():
            return self - (other * (self / other))

    @operation
    def __lt__(self: Nat, other: Nat) -> Bool:
        # 0 < 0 = false
        if (self ==  Nat.zero()) and (other == Nat.zero()):
            return Bool.false()

        # 0 < suc(y) = true
        if (self == Nat.zero()) and (other, Nat.suc(var.y)):
            return Bool.true()

        # suc(x) < 0 = false
        if (self == Nat.suc(var.x)) and (other == Nat.zero()):
            return Bool.false()

        # suc(x) < suc(y) = x < y
        if (self == Nat.suc(var.x)) and (other == Nat.suc(var.y)):
            return var.x < var.y

    @operation
    def __le__(self: Nat, other: Nat) -> Bool:
        if self == other:
            return Bool.true()
        return self < other

    @operation
    def __ge__(self: Nat, other: Nat) -> Bool:
        if self == other:
            return Bool.true()
        return self > other

    @operation
    def __gt__(self: Nat, other: Nat) -> Bool:
        return ~(self <= other)

    def _as_int(self):
        if self._generator == Nat.zero:
            return 0
        elif self._generator == Nat.suc:
            return 1 + self._generator_args['self']._as_int()

    def __str__(self):
        return '%s(%i)' % (self.__class__.__name__, self._as_int())
