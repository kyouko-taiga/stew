class StewError(Exception):
    """Baseclass fot all Stew exceptions."""


class ArgumentError(StewError):
    """
    Raised when a sort initialization, generator or operation is applied with
    inappropriated arguments.
    """


class MatchError(StewError):
    """
    Internal exception that is raised when an operation attempts to access a
    variable in a :class:`MatchResult` that wasn't matched.
    """


class RewritingError(StewError):
    """
    Raised when an operation couldn't be rewritten by an operation.
    """
