# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License. See LICENSE in the project root
# for license information.

__author__ = "Microsoft Corporation <ptvshelp@microsoft.com>"
__version__ = "4.0.0a1"

import sys


# Py3 compat - alias unicode to str, and xrange to range
try:
    unicode  # noqa
except NameError:
    unicode = str
try:
    xrange  # noqa
except NameError:
    xrange = range


class SafeRepr(object):
    # String types are truncated to maxstring_outer when at the outer-
    # most level, and truncated to maxstring_inner characters inside
    # collections.
    maxstring_outer = 2 ** 16
    maxstring_inner = 30
    if sys.version_info >= (3, 0):
        string_types = (str, bytes)
        set_info = (set, '{', '}', False)
        frozenset_info = (frozenset, 'frozenset({', '})', False)
    else:
        string_types = (str, unicode)
        set_info = (set, 'set([', '])', False)
        frozenset_info = (frozenset, 'frozenset([', '])', False)

    # Collection types are recursively iterated for each limit in
    # maxcollection.
    maxcollection = (15, 10)

    # Specifies type, prefix string, suffix string, and whether to include a
    # comma if there is only one element. (Using a sequence rather than a
    # mapping because we use isinstance() to determine the matching type.)
    collection_types = [
        (tuple, '(', ')', True),
        (list, '[', ']', False),
        frozenset_info,
        set_info,
    ]
    try:
        from collections import deque
        collection_types.append((deque, 'deque([', '])', False))
    except Exception:
        pass

    # type, prefix string, suffix string, item prefix string,
    # item key/value separator, item suffix string
    dict_types = [(dict, '{', '}', '', ': ', '')]
    try:
        from collections import OrderedDict
        dict_types.append((OrderedDict, 'OrderedDict([', '])', '(', ', ', ')'))
    except Exception:
        pass

    # All other types are treated identically to strings, but using
    # different limits.
    maxother_outer = 2 ** 16
    maxother_inner = 30

    def __call__(self, obj):
        try:
            return ''.join(self._repr(obj, 0))
        except Exception:
            try:
                return 'An exception was raised: %r' % sys.exc_info()[1]
            except Exception:
                return 'An exception was raised'

    def _repr(self, obj, level):
        '''Returns an iterable of the parts in the final repr string.'''

        try:
            obj_repr = type(obj).__repr__
        except Exception:
            obj_repr = None

        def has_obj_repr(t):
            r = t.__repr__
            try:
                return obj_repr == r
            except Exception:
                return obj_repr is r

        for t, prefix, suffix, comma in self.collection_types:
            if isinstance(obj, t) and has_obj_repr(t):
                return self._repr_iter(obj, level, prefix, suffix, comma)

        for t, prefix, suffix, item_prefix, item_sep, item_suffix in self.dict_types:  # noqa
            if isinstance(obj, t) and has_obj_repr(t):
                return self._repr_dict(obj, level, prefix, suffix,
                                       item_prefix, item_sep, item_suffix)

        for t in self.string_types:
            if isinstance(obj, t) and has_obj_repr(t):
                return self._repr_str(obj, level)

        if self._is_long_iter(obj):
            return self._repr_long_iter(obj)

        return self._repr_other(obj, level)

    # Determines whether an iterable exceeds the limits set in
    # maxlimits, and is therefore unsafe to repr().
    def _is_long_iter(self, obj, level=0):
        try:
            # Strings have their own limits (and do not nest). Because
            # they don't have __iter__ in 2.x, this check goes before
            # the next one.
            if isinstance(obj, self.string_types):
                return len(obj) > self.maxstring_inner

            # If it's not an iterable (and not a string), it's fine.
            if not hasattr(obj, '__iter__'):
                return False

            # Iterable is its own iterator - this is a one-off iterable
            # like generator or enumerate(). We can't really count that,
            # but repr() for these should not include any elements anyway,
            # so we can treat it the same as non-iterables.
            if obj is iter(obj):
                return False

            # xrange reprs fine regardless of length.
            if isinstance(obj, xrange):
                return False

            # numpy and scipy collections (ndarray etc) have
            # self-truncating repr, so they're always safe.
            try:
                module = type(obj).__module__.partition('.')[0]
                if module in ('numpy', 'scipy'):
                    return False
            except Exception:
                pass

            # Iterables that nest too deep are considered long.
            if level >= len(self.maxcollection):
                return True

            # It is too long if the length exceeds the limit, or any
            # of its elements are long iterables.
            if hasattr(obj, '__len__'):
                try:
                    size = len(obj)
                except Exception:
                    size = None
                if size is not None and size > self.maxcollection[level]:
                    return True
                return any((self._is_long_iter(item, level + 1) for item in obj))  # noqa
            return any(i > self.maxcollection[level] or self._is_long_iter(item, level + 1) for i, item in enumerate(obj))  # noqa

        except Exception:
            # If anything breaks, assume the worst case.
            return True

    def _repr_iter(self, obj, level, prefix, suffix,
                   comma_after_single_element=False):
        yield prefix

        if level >= len(self.maxcollection):
            yield '...'
        else:
            count = self.maxcollection[level]
            yield_comma = False
            for item in obj:
                if yield_comma:
                    yield ', '
                yield_comma = True

                count -= 1
                if count <= 0:
                    yield '...'
                    break

                for p in self._repr(item, 100 if item is obj else level + 1):
                    yield p
            else:
                if comma_after_single_element:
                    if count == self.maxcollection[level] - 1:
                        yield ','
        yield suffix

    def _repr_long_iter(self, obj):
        try:
            obj_repr = '<%s, len() = %s>' % (type(obj).__name__, len(obj))
        except Exception:
            try:
                obj_repr = '<' + type(obj).__name__ + '>'
            except Exception:
                obj_repr = '<no repr available for object>'
        yield obj_repr

    def _repr_dict(self, obj, level, prefix, suffix,
                   item_prefix, item_sep, item_suffix):
        if not obj:
            yield prefix + suffix
            return
        if level >= len(self.maxcollection):
            yield prefix + '...' + suffix
            return

        yield prefix

        count = self.maxcollection[level]
        yield_comma = False

        try:
            sorted_keys = sorted(obj)
        except Exception:
            sorted_keys = list(obj)

        for key in sorted_keys:
            if yield_comma:
                yield ', '
            yield_comma = True

            count -= 1
            if count <= 0:
                yield '...'
                break

            yield item_prefix
            for p in self._repr(key, level + 1):
                yield p

            yield item_sep

            try:
                item = obj[key]
            except Exception:
                yield '<?>'
            else:
                for p in self._repr(item, 100 if item is obj else level + 1):
                    yield p
            yield item_suffix

        yield suffix

    def _repr_str(self, obj, level):
        return self._repr_obj(obj, level,
                              self.maxstring_inner, self.maxstring_outer)

    def _repr_other(self, obj, level):
        return self._repr_obj(obj, level,
                              self.maxother_inner, self.maxother_outer)

    def _repr_obj(self, obj, level, limit_inner, limit_outer):
        try:
            obj_repr = repr(obj)
        except Exception:
            try:
                obj_repr = object.__repr__(obj)
            except Exception:
                try:
                    obj_repr = '<no repr available for ' + type(obj).__name__ + '>'  # noqa
                except Exception:
                    obj_repr = '<no repr available for object>'

        limit = limit_inner if level > 0 else limit_outer

        if limit >= len(obj_repr):
            yield obj_repr
            return

        # Slightly imprecise calculations - we may end up with a string that is
        # up to 3 characters longer than limit. If you need precise formatting,
        # you are using the wrong class.
        left_count, right_count = max(1, int(2 * limit / 3)), max(1, int(limit / 3))  # noqa

        yield obj_repr[:left_count]
        yield '...'
        yield obj_repr[-right_count:]

    def _selftest(self):
        # Test the string limiting somewhat automatically
        tests = []
        tests.append((7, 9, 'A' * (5)))
        tests.append((self.maxstring_outer + 3, self.maxstring_inner + 3 + 2, 'A' * (self.maxstring_outer + 10)))  # noqa
        if sys.version_info >= (3, 0):
            tests.append((self.maxstring_outer + 4, self.maxstring_inner + 4 + 2, bytes('A', 'ascii') * (self.maxstring_outer + 10)))  # noqa
        else:
            tests.append((self.maxstring_outer + 4, self.maxstring_inner + 4 + 2, unicode('A') * (self.maxstring_outer + 10)))  # noqa

        for limit1, limit2, value in tests:
            assert len(self(value)) <= limit1 <= len(repr(value)), (len(self(value)), limit1, len(repr(value)), value)  # noqa
            assert len(self([value])) <= limit2 <= len(repr([value])), (len(self([value])), limit2, len(repr([value])), self([value]))  # noqa

        def test(source, expected):
            actual = self(source)
            if actual != expected:
                print("Source " + repr(source))
                print("Expect " + expected)
                print("Actual " + actual)
                print("")
                assert False

        def re_test(source, pattern):
            import re
            actual = self(source)
            if not re.match(pattern, actual):
                print("Source  " + repr(source))
                print("Pattern " + pattern)
                print("Actual  " + actual)
                print("")
                assert False

        for ctype, _prefix, _suffix, comma in self.collection_types:
            for i in range(len(self.maxcollection)):
                prefix = _prefix * (i + 1)
                if comma:
                    suffix = _suffix + ("," + _suffix) * i
                else:
                    suffix = _suffix * (i + 1)
                #print("ctype = " + ctype.__name__ + ", maxcollection[" +
                #      str(i) + "] == " + str(self.maxcollection[i]))
                c1 = ctype(range(self.maxcollection[i] - 1))
                inner_repr = prefix + ', '.join(str(j) for j in c1)
                c2 = ctype(range(self.maxcollection[i]))
                c3 = ctype(range(self.maxcollection[i] + 1))
                for j in range(i):
                    c1, c2, c3 = ctype((c1,)), ctype((c2,)), ctype((c3,))
                test(c1, inner_repr + suffix)
                test(c2, inner_repr + ", ..." + suffix)
                test(c3, inner_repr + ", ..." + suffix)

                if ctype is set:
                    # Cannot recursively add sets to sets
                    break

        # Assume that all tests apply equally to all iterable types and only
        # test with lists.
        c1 = list(range(self.maxcollection[0] * 2))
        c2 = [c1 for _ in range(self.maxcollection[0] * 2)]
        c1_expect = '[' + ', '.join(str(j) for j in range(self.maxcollection[0] - 1)) + ', ...]'  # noqa
        test(c1, c1_expect)
        c1_expect2 = '[' + ', '.join(str(j) for j in range(self.maxcollection[1] - 1)) + ', ...]'  # noqa
        c2_expect = '[' + ', '.join(c1_expect2 for _ in range(self.maxcollection[0] - 1)) + ', ...]'  # noqa
        test(c2, c2_expect)

        # Ensure dict keys and values are limited correctly
        d1 = {}
        d1_key = 'a' * self.maxstring_inner * 2
        d1[d1_key] = d1_key
        re_test(d1, "{'a+\.\.\.a+': 'a+\.\.\.a+'}")
        d2 = {d1_key: d1}
        re_test(d2, "{'a+\.\.\.a+': {'a+\.\.\.a+': 'a+\.\.\.a+'}}")
        d3 = {d1_key: d2}
        if len(self.maxcollection) == 2:
            re_test(d3, "{'a+\.\.\.a+': {'a+\.\.\.a+': {\.\.\.}}}")
        else:
            re_test(d3, "{'a+\.\.\.a+': {'a+\.\.\.a+': {'a+\.\.\.a+': 'a+\.\.\.a+'}}}")  # noqa

        # Ensure empty dicts work
        test({}, '{}')

        # Ensure dict keys are sorted
        d1 = {}
        d1['c'] = None
        d1['b'] = None
        d1['a'] = None
        test(d1, "{'a': None, 'b': None, 'c': None}")

        if sys.version_info >= (3, 0):
            # Ensure dicts with unsortable keys do not crash
            d1 = {}
            for _ in range(100):
                d1[object()] = None
            try:
                list(sorted(d1))
                assert False, "d1.keys() should be unorderable"
            except TypeError:
                pass
            self(d1)

        # Test with objects with broken repr implementations
        class TestClass(object):
            def __repr__(self):
                raise NameError
        try:
            repr(TestClass())
            assert False, "TestClass().__repr__ should have thrown"
        except NameError:
            pass
        self(TestClass())

        # Test with objects with long repr implementations
        class TestClass(object):
            repr_str = '<' + 'A' * self.maxother_outer * 2 + '>'

            def __repr__(self):
                return self.repr_str
        re_test(TestClass(), r'\<A+\.\.\.A+\>')

        # Test collections that don't override repr
        class TestClass(dict):
            pass
        test(TestClass(), '{}')

        class TestClass(list):
            pass
        test(TestClass(), '[]')

        # Test collections that override repr
        class TestClass(dict):
            def __repr__(self):
                return 'MyRepr'
        test(TestClass(), 'MyRepr')

        class TestClass(list):
            def __init__(self, iter=()):
                list.__init__(self, iter)

            def __repr__(self):
                return 'MyRepr'
        test(TestClass(), 'MyRepr')

        # Test collections and iterables with long repr
        test(TestClass(xrange(0, 15)), 'MyRepr')
        test(TestClass(xrange(0, 16)), '<TestClass, len() = 16>')
        test(TestClass([TestClass(xrange(0, 10))]), 'MyRepr')
        test(TestClass([TestClass(xrange(0, 11))]), '<TestClass, len() = 1>')

        # Test strings inside long iterables
        test(TestClass(['a' * (self.maxcollection[1] + 1)]),
             'MyRepr')
        test(TestClass(['a' * (self.maxstring_inner + 1)]),
             '<TestClass, len() = 1>')

        # Test range
        if sys.version[0] == '2':
            range_name = 'xrange'
        else:
            range_name = 'range'
        test(xrange(1, self.maxcollection[0] + 1),
             '%s(1, %s)' % (range_name, self.maxcollection[0] + 1))

        # Test directly recursive collections
        c1 = [1, 2]
        c1.append(c1)
        test(c1, '[1, 2, [...]]')
        d1 = {1: None}
        d1[2] = d1
        test(d1, '{1: None, 2: {...}}')

        # Find the largest possible repr and ensure it is below our arbitrary
        # limit (8KB).
        coll = '-' * (self.maxstring_outer * 2)
        for limit in reversed(self.maxcollection[1:]):
            coll = [coll] * (limit * 2)
        dcoll = {}
        for i in range(self.maxcollection[0]):
            dcoll[str(i) * self.maxstring_outer] = coll
        text = self(dcoll)
        #try:
        #    text_repr = repr(dcoll)
        #except MemoryError:
        #    print('Memory error raised while creating repr of test data')
        #    text_repr = ''
        #print('len(SafeRepr()(dcoll)) = ' + str(len(text)) +
        #      ', len(repr(coll)) = ' + str(len(text_repr)))
        assert len(text) < 8192

        # Test numpy types - they should all use their native reprs,
        # even arrays exceeding limits
        try:
            import numpy as np
        except ImportError:
            msg = 'WARNING! could not import numpy - skipping all numpy tests.'
            print(msg)
        else:
            test(np.int32(123),
                 repr(np.int32(123)))
            test(np.float64(123.456),
                 repr(np.float64(123.456)))
            test(np.zeros(self.maxcollection[0] + 1),
                 repr(np.zeros(self.maxcollection[0] + 1)))
