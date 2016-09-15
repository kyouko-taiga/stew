class AbstractSort(object):

    def __init__(self, implements=None):
        self.implements = implements

    @property
    def __sortname__(self):
        if self.implements is not None:
            if isinstance(self.implements, type):
                implementing = self.implements.__name__
            else:
                implementing = ', '.join(t.__name__ for t in self.implements)
            return '%s(%s)' % (self.__class__.__name__, implementing)

        else:
            return self.__class__.__name__ + '()'

    def __str__(self):
        return '<%s>' % self.__sortname__

    def __repr__(self):
        return repr(str(self))
