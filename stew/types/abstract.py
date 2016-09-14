from ..proxy import Proxy


class AbstractSort(object):

    def __init__(self, implements=None, default=None):
        self.implements = implements
        self.default = default

    @property
    def __name__(self):
        if self.implements is not None:
            if isinstance(self.implements, type):
                implementing = self.implements.__name__
            else:
                implementing = ', '.join(t.__name__ for t in self.implements)
            return '%s(%s)' % (self.__class__.__name__, implementing)

        else:
            return self.__class__.__name__ + '()'

    def __str__(self):
        return '<%s>' % self.__name__

    def __repr__(self):
        return repr(str(self))


class _AbstractSortProxy(Proxy):

    def __getattribute__(self, attr):
        if attr == '__implementation__':
            impl = object.__getattribute__(self, '__proxied__')
            return None if isinstance(impl, AbstractSort) else impl
        else:
            return super().__getattribute__(attr)

    def __setattr__(self, attr, value):
        if attr == '__implementation__':
            object.__setattr__(self, '__proxied__', value)
        else:
            super().__setattr__(self, attr, value)


def create_abstract_sort(implements=None, default=None):
    return _AbstractSortProxy(AbstractSort(implements=implements, default=default))
