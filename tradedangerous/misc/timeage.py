""" timeage provides methods for turning numeric representations of time
    into human-friendly 'age' strings.
"""
from __future__ import annotations
import datetime


def describe_age(age: float | int) -> str:
    """
        describe_age turns a duration in seconds into a text representation.

        >>> describe_age(0)
        'now'
        >>> describe_age(-99999999.999)
        'now'
        >>> describe_age(1.234)
        '<1 hr'
        >>> describe_age(3672)
        '1 hr'
        >>> describe_age(9999)
        '2 hrs'
        >>> describe_age(86400)
        '24 hrs'
        >>> describe_age(86400*2 - 1)
        '47 hrs'
        >>> describe_age(86400*2)
        '2 days'
        >>> describe_age(86400*90 - 1)
        '89 days'
        >>> describe_age(86400*90)
        '3 mths'
    """
    # Handle trivial
    if age <= 1.0:
        return "now"

    if age < 0:
        return "-" + describe_age(-age)

    hours = int(age / 3600)
    if hours < 1:
        return "<1 hr"
    if hours == 1:
        return "1 hr"
    if hours < 48:
        return f"{hours} hrs"
    days = int(hours / 24)
    if days < 90:
        return f"{days} days"
    
    return f"{int(days / 30)} mths"


def timedelta_to_age(delta: datetime.timedelta) -> str:
    """ timedelta_to_age returns an age representation of a datetime.timedelta. """
    return describe_age(delta.total_seconds())


def notz_datetime_to_age(when: datetime.datetime) -> str:
    """
        notz_datetime_to_age returns an age representation of a non-tz-aware datetime.datetime.
        @see datetime_to_age if you have timezone info in your datetime.
    """
    now = datetime.datetime.now()
    return timedelta_to_age(now - when)

def datetime_to_age(when: datetime.datetime) -> str:
    """
        datetime_to_age returns an age representation of a tz-aware datetime.datetime.
        @note requires datetimes to be timezone aware.
        @see notz_datetime_to_age
    """
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    return timedelta_to_age(now - when)
