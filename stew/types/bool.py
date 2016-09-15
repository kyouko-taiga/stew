from ..core import Sort, generator, operation


class Bool(Sort):

    @generator
    def true() -> Bool: pass

    @generator
    def false() -> Bool: pass

    @operation
    def __invert__(self: Bool) -> Bool:
        # ~true = false
        with self.matches(Bool.true()):
            yield Bool.false()

        # ~false = true
        with self.matches(Bool.false()):
            yield Bool.true()

    @operation
    def __and__(self: Bool, other: Bool) -> Bool:
        with self.stew.matches((self, Bool.true()), (other, Bool.true())):
            yield Bool.true()
        yield Bool.false()

    @operation
    def __or__(self: Bool, other: Bool) -> Bool:
        with self.matches(Bool.true()):
            yield Bool.true()
        with other.matches(Bool.true()):
            yield Bool.true()
        yield Bool.false()

    @operation
    def __xor__(self: Bool, other: Bool) -> Bool:
        with self.stew.matches((self, Bool.true()), (other, Bool.false())):
            yield Bool.true()
        with self.stew.matches((self, Bool.false()), (other, Bool.true())):
            yield Bool.true()
        yield Bool.false()
