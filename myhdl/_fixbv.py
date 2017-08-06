#  This file is part of the myhdl library, a Python package for using
#  Python as a Hardware Description Language.
#
#  Copyright (C) 2013 Christopher L. Felton
#
#  The myhdl library is free software; you can redistribute it and/or
#  modify it under the terms of the GNU Lesser General Public License as
#  published by the Free Software Foundation; either version 2.1 of the
#  License, or (at your option) any later version.
#
#  This library is distributed in the hope that it will be useful, but
#  WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
#  Lesser General Public License for more details.

#  You should have received a copy of the GNU Lesser General Public
#  License along with this library; if not, write to the Free Software
#  Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA

""" Module with the fixbv class """
from __future__ import print_function, absolute_import
import sys

import math
from myhdl._intbv import intbv
from myhdl._modbv import modbv
from myhdl._compat import integer_types


class FixedPointFormat(object):
    def __init__(self, wl, iwl, fwl=None):
        if fwl is None:
            fwl = wl-iwl-1
        assert wl == iwl+fwl+1, "Invalid %d %d %d" % (wl, iwl, fwl)
        self._wl, self._iwl, self._fwl = wl, iwl, fwl

    def __len__(self):
        return 3

    def __repr__(self):
        s = "FixedPointFormat(%d, %d, [%d])" % (self._wl, self._iwl, self._fwl)
        return s

    def __str__(self):
        s = "(%d, %d, [%d])" % (self._wl, self._iwl, self._fwl)
        return s

    def __getitem__(self, key):
        val = [self._wl, self._iwl, self._fwl][key]
        return val

    def __setitem__(self, key, val):
        if isinstance(key, (int)):
            keys, vals = [key], [val]
        elif isinstance(key, slice):
            keys = range(*key.indices(3))
            vals = val
        for k, v in zip(keys, vals):
            if k == 0:
                self._wl = v
            elif k == 1:
                self._iwl = v
            elif k == 2:
                self._fwl = v
            else:
                raise AssertionError("Invalid index %d %s" % (key, type(key)))

    def __eq__(self, other):
        cmp = True
        if isinstance(other, FixedPointFormat):
            for s, o in zip(self[:], other[:]):
                if s != o:
                    cmp = False
        else:
            cmp = False

        return cmp

    def __addsub__(self, other):
        """ Addition or Subtraction grows the format by one
        """
        assert isinstance(other, FixedPointFormat), \
            "Invalid type for other %s" % (type(other))

        iwl = max(self._iwl, other._iwl)+1
        fwl = max(self._fwl, other._fwl)
        wl = iwl+fwl+1
        return FixedPointFormat(wl, iwl, fwl)

    def __muldiv__(self, other):
        """ Multiplication and Division double the word size
        """
        assert isinstance(other, FixedPointFormat), \
            "Invalid type for other %s" % (type(other))
        wl = self._wl+other._wl
        fwl = self._fwl+other._fwl
        iwl = wl-fwl-1
        return FixedPointFormat(wl, iwl, fwl)

    def __add__(self, other):
        return self.__addsub__(other)

    def __sub__(self, other):
        return self.__addsub__(other)

    def __mul__(self, other):
        return self.__muldiv__(other)

    def __div__(self, other):
        return self.__muldiv__(other)


class fixbv(modbv):

    def __init__(self, val, min=None, max=None, res=None,
                 round_mode=None, overflow_mode=None):

        # round mode and overflow mode
        if round_mode is None:
            self._round_mode = 'floor'
        else:
            self._round_mode = round_mode

        if overflow_mode is None:
            self._overflow_mode = 'saturate'
        else:
            self._overflow_mode = overflow_mode

        format = None
        val = float(val)
        self._ifval = val   # save the initial value

        if None in (min, max, res):
            # @todo: this is not working correctly
            # min,max,res = self._calc_min_max_res(val)
            self._val = None
            return

        # validate the range and resolution
        if max < 1 or abs(min) < 1:
            raise ValueError("Maximum and Minimum has to be 1 or greater")
        if max is None or not isinstance(max, integer_types + (float,)):
            raise ValueError("Maximum has to be provided, max=%s" % (str(max)))
        if min is None or not isinstance(min, integer_types + (float,)):
            raise ValueError("Minimum has to be provided, min=%s" % (str(min)))
        if res is None:
            raise ValueError("Resolution has to be provided, res=%s"
                             % (str(res)))
        elif res <= 0 or res > 1:
            raise ValueError("Resolution must be in range (0, 1], res=%s"
                             % (str(res)))

        # calculate the integer and fractional widths
        ival = abs(min) if abs(min) > max else max
        niwl, nfwl = self._calc_width(ival, res)
        nwl = niwl+nfwl+1
        self._W = FixedPointFormat(nwl, niwl, nfwl)
        self.__min, self.__max = min, max

        # We want a signed number but we don't want to force any
        # notion of a fixed point value to the lower levels.  From
        # the intbv point of view it only knows that it is a signed
        # integer, this is enough information to enforce the rules.
        # But intbv the min and max are the min/max for the number
        # of bits we are creating.
        nrbits = nwl    # self._iwl + self._fwl + 1

        # these will be overwritten by intbv
        self._min = -1 * 2**(nrbits-1)
        self._max = 2**(nrbits-1)
        fxval = self._from_float(val)
        intbv.__init__(self, fxval, min=self._min, max=self._max)
        # self._fval = val

        if self._nrbits != nrbits:
            errstr = "ERROR: intbv num of bits != fixbv num of bits %d,%d" \
                    % (self._nrbits, nrbits)
            raise ValueError(errstr)

        # make sure things were setup ok
        self._handleBounds()

    def _handleBounds(self):
        """ check bounds """
        intbv._handleBounds(self)

    ######################################################################
    # properties
    ######################################################################
    @property
    def format(self):
        return tuple(self._W[:])

    @property
    def res(self):
        _res = 2.0 ** (-1*self._W._fwl)
        return _res

    @property
    def max(self):
        return self.__max

    @property
    def min(self):
        return self.__min

    ######################################################################
    # overloaded functions
    ######################################################################
    def __copy__(self):
        min, max, res = self._minmaxres()
        retval = fixbv(self._to_float(), min, max, res,
                       round_mode=self._round_mode,
                       overflow_mode=self._overflow_mode)
        return retval

    def __deepcopy__(self, visit):
        min, max, res = self._minmaxres()
        retval = fixbv(self._to_float(), min, max, res,
                       round_mode=self._round_mode,
                       overflow_mode=self._overflow_mode)
        return retval

    def __getitem__(self, key):
        if isinstance(key, (tuple, list)):
            fwl = key[2] if len(key) == 3 else key[0]-key[1]-1
            res = 2**-(fwl)
            nmax = 2**(key[1])
            nmin = -nmax
            if self._val is None:
                fval = self._ifval
            else:
                fval = self._to_float()
            return fixbv(fval, min=nmin, max=nmax, res=res)
        else:
            # @todo: check for negative index and convert
            #        to the underlying intbv indexes
            slc = intbv(self._val, _nrbits=self._nrbits)
            return slc.__getitem__(key)

    def __setitem__(self, key, val):
        if isinstance(val, fixbv):
            assert key == slice(None, None, None)

            v = fixbv._round(val, self._W, self._round_mode)
            v = fixbv._overflow(v, self._W, self._overflow_mode)
        else:
            v = val
        # @todo: convert negative keys to the correct bit index
        intbv.__setitem__(self, key, v)

    def __repr__(self):
        # fixbv(_fval, format=(%d,%d,%d))
        rs = "fixbv(%f, " % (self._to_float())
        wl, iwl, fwl = self._W[:]
        fwl = wl-iwl-1
        rs += " format=(%d,%d,%d), " % (wl, iwl, fwl)
        rs += ")"
        # @todo: ? add integer value somewhere?
        return rs

    def __str__(self):
        # For very large bit widths the resolution of the fixbv
        # will exceed those of a 64 bit float value.  Need to use
        # something more power when "displaying" the values, use the
        # Decimal object to create a more accurate version of the
        # underlying value.
        # @todo: use *Decimal* and determine the number of of
        #        10s digits required.
        #         intp = Decimal(self._iival) + 2**Decimal(-self._ifval)
        fstr = "%f" % (self._to_float())
        return fstr

    def __hex__(self):
        return hex(self._val)

    def __float__(self):
        return self._to_float()     # self._fval

    def __ord__(self):
        return self._val

    def __add__(self, other):
        if isinstance(other, fixbv):
            iW = self._W + other._W
        else:
            # Solve the case if `type(other) is Signal`
            return other.__radd__(self)    # TODO: Write test for it
            # raise TypeError("other must be fixbv not %s" % (type(other)))

        retval = fixbv(0)[iW[:]]

        if self._W._fwl < other._W._fwl:
            a = (self._val << (other._W._fwl - self._W._fwl))
            b = other._val
        else:
            a = self._val
            b = (other._val << (self._W._fwl - other._W._fwl))

        retval._val = a + b
        retval._handleBounds()
        return retval

    def __sub__(self, other):
        if isinstance(other, fixbv):
            iW = self._W + other._W
        else:
            # Solve the case if `type(other) is Signal`
            return other.__rsub__(self)    # TODO: Write test for it
            # raise TypeError("other must be fixbv not %s" % (type(other)))

        retval = fixbv(0)[iW[:]]

        if self._W._fwl < other._W._fwl:
            a = (self._val << (other._W._fwl - self._W._fwl))
            b = other._val
        else:
            a = self._val
            b = (other._val << (self._W._fwl - other._W._fwl))

        retval._val = a - b
        retval._handleBounds()
        return retval

    def __mul__(self, other):
        if isinstance(other, fixbv):
            iW = self._W * other._W
        else:
            # Solve the case if `type(other) is Signal`
            return other.__rmul__(self)    # TODO: Write test for it
            # raise TypeError("other must be fixbv not %s" % (type(other)))

        retval = fixbv(0)[iW[:]]
        retval._val = self._val * other._val
        retval._handleBounds()
        return retval

    def __pow__(self, other):
        # @todo: a better way to do this, add __pow__ to FixedPointFormat?
        # TODO: Deal with the case if other < 0 or other == 0
        if not isinstance(other, integer_types):
            raise TypeError("other must be integer type not %s" %
                            (type(other)))
        if other < 2:
            iW = self._W
        else:
            iW = self._W * self._W
            for ii in range(2, other):
                iW = iW * self._W
        retval = fixbv(0)[iW[:]]
        retval._val = self._val ** other
        retval._handleBounds()
        return retval

    # all comparisons must be on aligned types
    def __eq__(self, other):
        if isinstance(other, fixbv):
            pass
        else:
            # Solve the case if `type(other) is Signal`
            return other.__eq__(self)    # TODO: Write test for it
            # raise TypeError("other must be fixbv not %s" % (type(other)))

        if self._W._fwl < other._W._fwl:
            a = (self._val << (other._W._fwl - self._W._fwl))
            b = other._val
        else:
            a = self._val
            b = (other._val << (self._W._fwl - other._W._fwl))

        return a == b

    def __ne__(self, other):
        if isinstance(other, fixbv):
            pass
        else:
            # Solve the case if `type(other) is Signal`
            return other.__ne__(self)    # TODO: Write test for it
            # raise TypeError("other must be fixbv not %s" % (type(other)))

        if self._W._fwl < other._W._fwl:
            a = (self._val << (other._W._fwl - self._W._fwl))
            b = other._val
        else:
            a = self._val
            b = (other._val << (self._W._fwl - other._W._fwl))

        return a != b

    def __gt__(self, other):
        if isinstance(other, fixbv):
            pass
        else:
            # Solve the case if `type(other) is Signal`
            return other.__le__(self)    # TODO: Write test for it
            # raise TypeError("other must be fixbv not %s" % (type(other)))

        if self._W._fwl < other._W._fwl:
            a = (self._val << (other._W._fwl - self._W._fwl))
            b = other._val
        else:
            a = self._val
            b = (other._val << (self._W._fwl - other._W._fwl))

        return a > b

    def __ge__(self, other):
        if isinstance(other, fixbv):
            pass
        else:
            # Solve the case if `type(other) is Signal`
            return other.__lt__(self)    # TODO: Write test for it
            # raise TypeError("other must be fixbv not %s" % (type(other)))

        if self._W._fwl < other._W._fwl:
            a = (self._val << (other._W._fwl - self._W._fwl))
            b = other._val
        else:
            a = self._val
            b = (other._val << (self._W._fwl - other._W._fwl))

        return a >= b

    def __lt__(self, other):
        if isinstance(other, fixbv):
            pass
        else:
            # Solve the case if `type(other) is Signal`
            return other.__ge__(self)    # TODO: Write test for it
            # raise TypeError("other must be fixbv not %s" % (type(other)))

        if self._W._fwl < other._W._fwl:
            a = (self._val << (other._W._fwl - self._W._fwl))
            b = other._val
        else:
            a = self._val
            b = (other._val << (self._W._fwl - other._W._fwl))

        return a < b

    def __le__(self, other):
        if isinstance(other, fixbv):
            pass
        else:
            # Solve the case if `type(other) is Signal`
            return other.__gt__(self)    # TODO: Write test for it
            # raise TypeError("other must be fixbv no t%s" % (type(other)))

        if self._W._fwl < other._W._fwl:
            a = (self._val << (other._W._fwl - self._W._fwl))
            b = other._val
        else:
            a = self._val
            b = (other._val << (self._W._fwl - other._W._fwl))

        return a <= b

    ######################################################################
    # private methods
    ######################################################################
    def _minmaxres(self):
        """ get the min, max, res """
        wl, iwl, fwl = self.format
        max, min, res = 2**(iwl), -2**(iwl), 2**(-fwl)
        return min, max, res

    def _calc_width(self, val, res=0):
        """Caclulate the iwl and fwl required for the value
        @todo: this function is not working!
        """
        frac, integer = math.modf(val)

        if res < frac or frac == 0:
            frac = res

        if abs(integer) == 0:
            iwl = 0
        else:
            iwl = math.ceil(math.log(abs(integer), 2))

        if frac == 0:
            fwl = 0
        else:
            fwl = math.ceil(math.log(frac**-1, 2))

        return (int(iwl), int(fwl))

    def _calc_min_max_res(self, fval):
        """Given floating point number calculate min, max and resolution
        Given a floating point number calculate the resolution required to
        represent the floating-point in a fixed-point number.
        """
        if fval == 0:
            inbits = 1
            fnbits = 1
        else:
            frac, integer = math.modf(fval)
            frac = abs(frac)
            integer = abs(integer)
            try:
                # adds an extra bit
                if integer == 0:
                    inbits = 1
                else:
                    inbits = int(abs(math.floor(math.log(integer, 2)))) + 1

                # adds an extra bit
                if frac == 0:
                    fnbits = 1
                else:
                    fnbits = int(abs(math.floor(math.log(frac, 2)))) + 1
            except:
                print("Fractional %s Integer %s" % (frac, integer))
                print("Unexpected error:", sys.exc_info()[0])
                raise

        fnbits = 1 if fnbits == 0 else fnbits
        inbits = 1 if inbits == 0 else inbits
        max = 2**(inbits-1)
        min = -2**(inbits-1)
        res = 2**(-fnbits)

        # make sure limits are still applicable for the rounded
        # version of fval if the value doesn't fit need an extra
        # integer bit.  This functions is mainly used if bit
        # constraints are not give (determine bit contraints
        # from value).  Adding extra bit (case of round_mode=truncate)
        # is ok.
        if round(fval) >= max or round(fval) <= min:
            max = 2**(inbits+1)
            min = -2**(inbits+1)

        return min, max, res

    def _from_float(self, val):
        """Convert float value to fixed point"""
        retval = fixbv._round(val, self._W, self._round_mode)
        # retval = self._overflow(retval)
        return int(retval)

    def _to_float(self):
        """Convert fixed point value to floating point number"""
        return float(self._val) / (2.0 ** self._W._fwl)

    ######################################################################
    # private static methods
    ######################################################################
    @staticmethod
    def _round(val, fmt, round_mode):
        """Round the value into a new format"""

        if isinstance(val, float):
            val *= 2.0**fmt._fwl

            if round_mode == 'ceil':
                retval = math.ceil(val)

            elif round_mode == 'fix':
                if val > 0:
                    retval = math.floor(val)
                else:
                    retval = math.ceil(val)

            elif round_mode == 'floor':
                retval = math.floor(val)

            elif round_mode == 'nearest':
                fval,ival = math.modf(val)
                if fval == .5 or fval == -.5:
                    retval = int(val+1) if val > 0 else int(val-1)
                else:
                    retval = round(val)

            elif round_mode == 'round':
                retval = round(val)

            elif round_mode == 'round_even' or round_mode == 'convergent':
                fval,ival = math.modf(val)
                abs_ival = int(abs(ival))
                sign = -1 if ival < 0 else 1

                if (abs(fval) - 0.5) == 0.0:
                    if abs_ival%2 == 0:
                        retval = abs_ival * sign
                    else:
                        retval = (abs_ival + 1) * sign
                else:
                    retval = round(val)

            else:
                raise ValueError("Invalid round mode %s" % round_mode)

            return int(retval)

        elif isinstance(val, fixbv):
            if val._W._fwl <= fmt._fwl:
                # Case when no rounding should apply
                retval = (val._val << (fmt._fwl - val._W._fwl))
                return retval

            # Explanation of the variables
            #
            # flag  A       BC  D
            # val   siiiii.ffffff
            # fmt   siiiii.ff
            #
            # A: sign_bit
            # B: least_reserve_bit
            # C: greatest_tail_bit
            # C-D: tail_bits
            # A-B: retval
            # |C-D|: round_bits

            round_bits = val._W._fwl - fmt._fwl

            sign_bit = (val._val >> (val._W._wl - 1)) & 1
            least_reserve_bit = (val._val >> round_bits) & 1
            greatest_tail_bit = (val._val >> (round_bits - 1)) & 1
            tail_bits = val._val & ((1 << round_bits) - 1)
            retval = (val._val >> round_bits)

            if round_mode == 'ceil':
                if tail_bits != 0:
                    retval += 1

            elif round_mode == 'floor':
                pass

            elif round_mode == 'fix':
                # Ceil for negatives and floor for non-negatives
                if sign_bit == 1 and tail_bits != 0:
                    retval += 1

            elif round_mode == 'nearest':
                if sign_bit == 0:
                    # positive
                    if greatest_tail_bit == 1:
                        retval += 1
                else:
                    # negative
                    middle = (1 << (round_bits - 1))
                    if tail_bits > middle:
                        retval += 1

            elif round_mode in ('round', 'round_even', 'convergent'):
                middle = (1 << (round_bits - 1))
                if sign_bit == 0:
                    # positive
                    if tail_bits == middle:
                        # halfway
                        if least_reserve_bit == 1:
                            # odd number
                            retval += 1
                    elif tail_bits > middle:
                        retval += 1
                else:
                    # negative
                    if tail_bits == middle:
                        # halfway
                        if least_reserve_bit == 1:
                            # odd number
                            retval += 1
                    elif tail_bits > middle:
                        retval += 1

            else:
                raise ValueError("Invalid round mode %s" % round_mode)

            return retval

        else:
            raise TypeError("%s is neither float nor fixbv" % type(val))

    @staticmethod
    def _overflow(val, fmt, overflow_mode):
        wl, iwl, fwl = fmt
        if isinstance(val, fixbv):
            val = val._val
            mm = 2 ** (wl - 1)
        elif isinstance(val, integer_types):
            mm = 2 ** (wl - 1)
        elif isinstance(val, float):
            mm = 2 ** iwl
        else:
            raise TypeError("%s is neither float nor fixbv" % type(val))

        mmin, mmax = -mm, mm

        if overflow_mode == 'saturate':
            if val >= mmax:
                retval = mmax-1
            elif val <= mmin:
                retval = mmin
            else:
                retval = val
        elif overflow_mode == 'ring' or overflow_mode == 'wrap':
            if isinstance(val, float):
                retval = math.fmod(val - mmin, mmax - mmin) + mmin
            else:
                retval = (val - mmin) % (mmax - mmin) + mmin
        else:
            raise ValueError("Invalid overflow mode %s" % overflow_mode)

        return retval

    ######################################################################
    # public methods
    ######################################################################
    def int(self):
        """ Retrieve the integer portion of the fixed-point
        This function is convertible to V*.  This will return
        the integer portion as an integer.
        """
        return self._val >> self._W._fwl

    def frac(self):
        """ Retrieve the fractional portion of hte fixed-point
        This funciton is convertible to V*.  This will return the
        fraction portion as an integer.
        """
        return self._val & ((1 << self._W._fwl) - 1)
