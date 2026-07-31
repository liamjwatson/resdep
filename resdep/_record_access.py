#!/usr/bin/env python3
"""
File: resdep/_record_access.py
DateTime: Tue Jul 28 11:39:00 2026
Last checked in by: watsonl

Description
Record access for use with resdep ioc state machine.
Cribbed from IMBL - keep aligned or create separate common module.
"""             

import functools
import sys
import devsup.db

# print to standard error.
#
errput = functools.partial(print, file=sys.stderr)

# Message prefix
#
iam = "record access:"


# -----------------------------------------------------------------------------
#
class RecordAccess:
    """
    This class provides a basic wrapper around devsup.db.Record usable with
    local records, i.e. those hosted on this IOC, that allows us to read from
    and write to the records.

    On write, the wrapper causes Passive record to process,
    a quazi "RECORD PP" operation.

    Note: this can be a singular record or multiple records.
    """

    total = 0
    found = 0

    def __init__(self, record_name):
        RecordAccess.total += 1

        self._record_name = record_name
        self._reference = None
        self._last_value = None

        if isinstance(record_name, str):
            try:
                self._reference = devsup.db.getRecord(record_name)
            except ValueError as e:
                errput(f"*** {e}: {record_name}")
                self._reference = None

        elif isinstance(record_name, tuple):
            # Assummed to be a tuple of record names
            #
            try:
                ref_list = []
                for rec_name in record_name:
                    ref = devsup.db.getRecord(rec_name)
                    ref_list.append(ref)
                self._reference = tuple(ref_list)
            except ValueError as e:
                errput(f"*** {e}: {rec_name}")
                self._reference = None

        else:
            type_name = record_name.__class__.__name__
            raise TypeError(
                    f"{iam} Expecting str or tuple(of str), got: {type_name}"
            )

        if self._reference is not None:
            RecordAccess.found += 1

    @property
    def name(self):
        return self._record_name

    @property
    def okay(self):
        return self._reference is not None

    def __str__(self):
        if self.okay:
            extra = " (okay)"
        else:
            extra = " (does not exist)"
        return f"{self.name}{extra}"

    @property
    def value(self):
        if not self.okay:
            errput(f"{iam} {self.name} wrapper is None")
            result = None

        elif isinstance(self._reference, tuple):
            result = []
            for ref in self._reference:
                result.append(ref.VAL)
            result = tuple(result)

        else:
            # must be a devsup.db.Record singleton
            #
            if self._reference is not None:
                result = self._reference.VAL

        return result

    @value.setter
    def value(self, new_value):
        if not self.okay:
            errput(f"{iam} {self.name} wrapper is None")
            return

        if isinstance(self._reference, tuple) != isinstance(new_value, tuple):
            ref_type = self._reference.__class__.__name__
            new_type = new_value.__class__.__name__
            raise TypeError(f"{self}: for {ref_type} got a {new_type}")

        if isinstance(self._reference, tuple):
            act = len(new_value)
            exp = len(self._reference)
            if act != exp:
                raise ValueError(f"""\
{self}: set value: actual length {act} \
does not match expected length {exp}""")

            for ref, val in zip(self._reference, new_value):
                ref.VAL = val
                ref.scan(sync=False, reason=None, force=0)

        else:
            # must be a devsup.db.Record singleton
            #
            if self._reference is not None:
                self._reference.VAL = new_value
                self._reference.scan(sync=False, reason=None, force=0)

    @property
    def severity(self):
        if not self.okay:
            errput(f"{iam} {self.name} wrapper is None")
            result = None

        elif isinstance(self._reference, tuple):
            result = self._reference[0].SEVR
            for ref in self._reference:
                result = max(result, ref.SEVR)

        else:
            # must be a devsup.db.Record singleton
            #
            if self._reference is not None:
                result = self._reference.SEVR

        return result

    def test_and_clear(self):
        """
        Test for and clear the value has changed status.
        """
        if self.okay:
            temp = self.value
            result = (temp != self._last_value)
            self._last_value = temp
        else:
            result = False
        return result

# end

