class Proxied(object):

    def __init__(self, obj):
        self.obj = obj

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return self.obj

    def __set__(self, instance, value):
        if instance is None:
            return self
        self.obj = value


class ProxyBase(type):

    _special_names = [
        '__abs__', '__add__', '__and__', '__call__', '__cmp__', '__coerce__',
        '__complex__', '__contains__', '__copy__', '__deepcopy__',
        '__delattr__', '__delitem__', '__delslice__', '__div__', '__divmod__',
        '__enter__', '__eq__', '__exit__', '__float__', '__floordiv__',
        '__ge__', '__getitem__', '__getslice__', '__gt__', '__hash__',
        '__hex__', '__iadd__', '__iand__', '__idiv__', '__idivmod__',
        '__ifloordiv__', '__ilshift__', '__imod__', '__imul__', '__index__',
        '__int__', '__invert__', '__ior__', '__ipow__', '__irshift__',
        '__isub__', '__iter__', '__itruediv__', '__ixor__', '__le__',
        '__len__', '__long__', '__lshift__', '__lt__', '__mod__', '__mul__',
        '__ne__', '__neg__', '__oct__', '__or__', '__pos__', '__pow__',
        '__radd__', '__rand__', '__rdiv__', '__rdivmod__', '__reduce__',
        '__reduce_ex__', '__repr__', '__reversed__', '__rfloorfiv__',
        '__rlshift__', '__rmod__', '__rmul__', '__ror__', '__rpow__',
        '__rrshift__', '__rshift__', '__rsub__', '__rtruediv__', '__rxor__',
        '__setitem__', '__setslice__', '__sub__', '__str__', '__truediv__',
        '__xor__', '__instancecheck__', '__subclasscheck__'
    ]

    def __new__(cls, classname, bases, attrs):
        def make_method(name):
            def method(self, *args, **kwargs):
                # Invoking special methods on the type object itself will fail
                # with a TypeError complaining about the descriptor missing an
                # argument. This can be avoided by bypassing the instance when
                # looking up special methods.
                proxied = object.__getattribute__(self, '__proxied__')
                return getattr(type(proxied), name)(proxied, *args, **kwargs)
            return method

        for name in cls._special_names:
            if name not in attrs:
                attrs[name] = make_method(name)

        return type.__new__(cls, classname, bases, attrs)


class Proxy(metaclass=ProxyBase):

    __slots__ = ('__proxied__', '__lazy__')

    def __init__(self, proxied=None, lazy=False):
        object.__setattr__(self, '__proxied__', proxied)
        object.__setattr__(self, '__lazy__', lazy)

    def _get_proxied_object(self):
        rv = object.__getattribute__(self, '__proxied__')
        if object.__getattribute__(self, '__lazy__'):
            return rv()
        return rv

    def __getattribute__(self, attr):
        proxied = object.__getattribute__(self, '_get_proxied_object')()
        return getattr(proxied, attr)

    def __setattr__(self, attr, value):
        proxied = object.__getattribute__(self, '_get_proxied_object')()
        setattr(proxied, attr, value)
