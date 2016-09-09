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
        '__xor__'
    ]

    def __new__(cls, classname, bases, attrs):
        def make_method(name):
            def method(self, *args, **kwargs):
                mtd = getattr(object.__getattribute__(self, '_proxied'), name)
                return mtd(*args, **kwargs)
            return method

        for name in cls._special_names:
            if name not in attrs:
                attrs[name] = make_method(name)

        attrs['_proxied'] = Proxied(None)

        return type.__new__(cls, classname, bases, attrs)


class Proxy(metaclass=ProxyBase):

    def __init__(self, proxied=None):
        pass
        # object.__setattr__(self, '_proxied', proxied)

    def __getattribute__(self, attr):
        if attr in object.__getattribute__(self, '__dict__'):
            # Since the requested attribute has been defined in the proxy,
            # we don't forward __getattribute__ to the proxied object.
            return object.__getattribute__(self, attr)
        else:
            return getattr(object.__getattribute__(self, '_proxied'), attr)

    def __setattr__(self, attr, value):
        if attr in object.__getattribute__(self, '__dict__'):
            # Since the requested attribute has been defined in the proxy,
            # we don't forward __setattr__ to the proxied object.
            object.__setattr__(self, attr, value)
        else:
            setattr(object.__getattribute__(self, '_proxied'), attr, value)
