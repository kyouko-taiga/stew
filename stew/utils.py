from collections.abc import Mapping

from .core import generator, operation


def make_function(name, domain, codomain):
    if isinstance(domain, Mapping):
        parameters = ', '.join('%s: %s' % (name, sort.__name__) for name, sort in domain.items())
    else:
        parameters = ', '.join('%s: %s' % (name, sort.__name__) for name, sort in domain)

    src = 'def %(name)s(%(parameters)s) -> %(codomain)s: pass' % {
        'name': name,
        'parameters': parameters,
        'codomain': codomain.__name__
    }

    eval_locals = {}
    scope = {sort.__name__: sort for sort in dict(domain).values()}
    scope[codomain.__name__] = codomain

    eval(compile(src, filename='<null>', mode='exec'), scope, eval_locals)
    return eval_locals[name]


def make_generator(name, domain, codomain):
    return generator(make_function(name, domain, codomain))


def make_operation(name, domain, codomain):
    fn = make_function(name, domain, codomain)
    fn._original = fn
    return operation(fn)
