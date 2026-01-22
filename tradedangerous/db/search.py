"""
search provides general methods for searching orm tables by name. These
are primarily provided as back-ends for TradeORM "lookup" methods.


# Previously:

The TradeDB lookup methods do some complex, crazy, fuzzy matching taking
word boundaries and punctuation etc into account.

We have no metrics on how widely used those are, but they would let
you search for SOL/Abraham Lincoln station with the input "hamlinc".

To do that we loaded all the instances so we could access their names.

TradeDB lookup methods are slow.


# New Approach:

Assume and reward users providing copy/pasted names (or passed via
variables, etc), by hot-pathing exact matches via the database with
no pre-load required.

Follow with near-match based on prefix, before falling back to highly
expensive fuzzy matching.

Fuzzy match is still slow because it has to bring every name into
Python to do the comparison, but it can still be faster than the
TradeDB approach because it uses like patterns to reduce the sheer
number of names retrieved.

That is:

   hamlinc -> %h%a%m%l%i%n%c%

While this is an expensive query, it is less expensive than having
SqlAlchemy surface every station name for python to perform a similar
filter.

With the Python filter applied to significantly less rows, there is
still a chance of performance gain.
"""
# pylint: disable=deprecated-typing-alias
from __future__ import annotations

from typing import NamedTuple, Type, TypeVar
import re
import typing

from sqlalchemy import Select, Result, select, and_, literal_column

from tradedangerous.tradeexcept import AmbiguityError

from .engine import Session
from .orm_models import NAME_LENGTH  # pylint: disable=unused-import  # noqa
from .orm_models import Category, Item, Station, System


if typing.TYPE_CHECKING:
    from typing import Any

# 'T' is used for the find methods as a generic "this table" parameter,
# 'G' is used for the find methods as a generic "group/parent table" parameter,
T = TypeVar("T", Category, Item, Station, System)
G = TypeVar("G", Category, System)


class Needle(NamedTuple):
    """Needle stores a search term decomposed into a normalized
    form (with spaces and punctuation removed) and a search
    pattern form (regex/like/etc)."""

    normalized: str         # the collapsed representation
    pattern: str            # a pattern to search for this sequence of individual characters
    left_anchored: bool
    right_anchored: bool


# Punctuation (non-whitespace) characters we will discard in normalization.
NORMALIZE_PUNCT = """/.,;:'"?!+-"""  # '-' must come last to be regex usable

# PUNCT_REGEX is a compiled store of a regex that strips consecutive space/punctation
# from a term to collapse it to alphanumeric-etc characters. Not ALL punctuation is removed.
PUNCT_REGEX = re.compile(r"[\s" + NORMALIZE_PUNCT + "]+")

# The 'sub' method of a compiled regex that escapes slash, percent, and understore
# to make a pattern safe for use in a like query.
LIKE_ESCAPING = re.compile(r"([\\%_])").sub


def escaped_for_like(term: str) -> str:
    """escaped_for_like returns term with any SQL 'LIKE' characters escaped."""
    return LIKE_ESCAPING(r"\\\1", term)


# python 3.12:
#  def name_startswith[T](table: T, pattern: str) -> Any:
def name_startswith(table: Type[T], pattern: str) -> Any:  # todo: correct type
    """escapes pattern for use in and returns a LIKE expression that matches
       table.name against pattern%.
    """
    return table.name.like(escaped_for_like(pattern) + "%", escape="\\")


def needle_from_term(key: str, *, key_prefix: str = "@", key_suffix: str = "/", pattern_prefix: str = "", pattern_suffix: str = "", pattern_wildcard: str = "%") -> Needle:
    """needle_from_term will produce a Needle instance for the given term, containing
    the normalized form and the search pattern based on the pattern's wildcard.

    key_prefix and key_suffix specify sequences that can be used to anchor the
    key to the beginning or end of the search.

    pattern_prefix and pattern_suffix specify sequences that should be injected
    to the search pattern to anchor it, if required. e.g. '^' and '$' if you want a regex.

    pattern_wildcard is the sequence the matcher needs to express "match 0+ something".
    """
    term, left_anchor, right_anchor = key, False, False

    # e.g. "@SOL" (if key_prefix is '@', the default)
    if term.startswith(key_prefix):
        left_anchor, term = True, term[1:]

    # e.g "SOL/" (if key_suffix is '/', the default); but only if that's the sole /
    # "bre\/\/" does not get this treatment
    if term.find(key_suffix) == len(term) - 1:
        right_anchor, term = True, term[:-1]

    if len(term) == 0:
        raise ValueError("empty field")
    # Enforce maximum search length per API contract
    if len(term) > NAME_LENGTH:
        raise ValueError(f"names are limited to {NAME_LENGTH} characters, got {len(term)}: {term[:NAME_LENGTH]}...")
    # this may be an overly aggressive constraint, but I'm trying to avoid wasting
    # the user's time with "'a' could match ..." or "' ' could match ...".
    if len(term) == 1:
        raise ValueError(f"overly ambiguous field: '{key}'")

    # split into characters which we then paper-doll with wildcards,
    # so that 'g m t a' can match 'gotta match them all' via '%g%m%t%a%'
    components = PUNCT_REGEX.split(term.lower())
    normalized = "".join(components)
    characters = list(normalized)
    # Escape each character individually so wildcards don't break escape sequences
    escaped_chars = [escaped_for_like(c) for c in characters]
    # @SOL is left-anchored, so it doesn't start with a wildcard.
    prefix = pattern_prefix if left_anchor else pattern_wildcard
    # SOL/ is right-anchored so it doesn't end with a wildcard.
    suffix = pattern_suffix if right_anchor else pattern_wildcard

    pattern = f"{prefix}{pattern_wildcard.join(escaped_chars)}{suffix}"

    return Needle(normalized, pattern, left_anchor, right_anchor)


# python 3.12:
#   def fuzzy_like[T, G](tdo: TradeORM, kind: str, term: str, table: T, parent: G | None = None) -> T:
def fuzzy_like(session: Session, kind: str, term: str, table: Type[T], group_table: Type[G] | None = None) -> T | None:
    """fuzzy_like attempts to find the a best match given a search key by finding
    all potential matches and then testing them for similarity/ambiguity.
    :param session: the database session to use for the query
    :param kind: textual label for the query (for error messages)
    :param term: the search term (name)
    :param table: the *Type* of the table to search, e.g. orm_models.Station
    :param group_table: optional *Type* of the parent/group table, e.g. orm_models.System
    :returns: the best-matching instance, or None if no matches found
    :raises AmbiguityError: if multiple matches are found that cannot be disambiguated
    """
    needle = needle_from_term(term)

    # when there's no category, it's a one-table query
    # if there's a parent we need to join it and concat the names (parent/table)
    if not group_table:
        query_field = table.name.label("match_name")
        query_from = select(table, query_field)
    else:
        # Use || operator which works on both SQLite and MariaDB for string concatenation
        query_field = (group_table.name + literal_column("'/'") + table.name).label("match_name")
        query_from = select(table, query_field).join(group_table)

    stmt = query_from.where(query_field.like(needle.pattern))
    rows: Result[Any] = session.execute(stmt)

    # 1: exact, 2: prefix-partial, 3: contains (as-is), 4: fuzzy
    matches: dict[int, list[T]] = {1: [], 2: [], 3: [], 4: []}

    for row in rows:
        match_name = row[1].lower()
        match_norm = PUNCT_REGEX.sub("", match_name)  # normalized
        if needle.normalized in match_norm:
            if needle.normalized == match_norm:
                score = 1  # exact match
            elif match_norm.startswith(needle.normalized):
                score = 2  # prefix partial
            else:
                score = 3  # contains as-is
        else:
            # fuzziest match (all characters occur in that order but not contiguous)
            # 'solr' <-willmatch- 's ol 4.1 ar'
            score = 4
        matches[score].append(row[0])

    # The match is considered unambiguous if we can find a bucket with a single
    # match before we find a bucket with > 1 match.
    for bucket in (1, 2, 3, 4):
        matched = matches[bucket]
        match len(matched):
            case 0:
                continue  # nothing in this bucket
            case 1:
                return matched[0]  # single item
            case _:
                raise AmbiguityError(kind, term, matched, key=lambda i: i.dbname())

    return None


# python 3.12:
#  def fast_find[T](tdo: TradeORM, kind: str, key: str, table: T) -> T | None:
def fast_find(session: Session, kind: str, key: str, table: Type[T]) -> T | None:
    """ search a single table for a term and find a unique match based on either
        exact-match or unique prefix match.

        :param session: the database session to use for the query
        :param kind: textual label for the query (for error messages)
        :param key: the search term (name)
        :param table: the *Type* of the table to search, e.g. orm_models.Station
        :returns: the best-matching instance, or None if no matches found
        :raises AmbiguityError: if multiple matches are found that cannot be disambiguated
    """
    if len(key) < 2:
        raise ValueError(f"overly ambiguous {kind} key: {key}")

    # exact matching
    stmt = select(table).where(table.name == key)
    rows = session.execute(stmt.limit(10)).all()
    if len(rows) == 1:
        return rows[0][0]
    if len(rows) > 1:
        models = [row[0] for row in rows]
        raise AmbiguityError(kind, key, models, key=lambda i: i.dbname())

    # prefix matching
    stmt = select(table).where(name_startswith(table, key))
    rows = session.execute(stmt.limit(10)).all()
    if len(rows) == 1:
        return rows[0][0]
    if len(rows) > 1:
        models = [row[0] for row in rows]
        raise AmbiguityError(kind, key, models, key=lambda i: i.dbname())
    return None


# python 3.12:
#  def fast_find_sub[T, G](tdo: TradeORM, key: str, table: T, group_table: G) -> T | G | None:
def fast_find_sub(session: Session, kind: str, key: str, table: Type[T], group_table: Type[G]) -> T | G | None:
    """ fast_find_sub attempts to find either a group (parent) or child item
        based on the given key. The key may express parent/child relationships
        using the '@' and '/' prefix/separator notations.

        :param session: the database session to use for the query
        :param kind: textual label for the query (for error messages)
        :param key: the search term (name)
        :param table: the *Type* of the child table to search, e.g. orm_models.Station
        :param group_table: the *Type* of the parent/group table, e.g. orm_models.System
        :returns: the best-matching table or group_table instance, or None if no matches found
        :raises AmbiguityError: if multiple matches are found that cannot be disambiguated
    """
    if len(key) < 2:
        raise ValueError(f"overly ambiguous search key: {key}")

    # Start with a list of most-likely simple, exact (fast) matches that most paths
    # will most likely want.
    exact_candidates: list[Select[Any]] = [
        select(table).where(table.name == key),
        select(group_table).where(group_table.name == key),
    ]
    # Those will be followed by slower, like-based matches - this relies
    # on our tables having no-case collation to avoid manipulating text case.
    like_candidates: list[Select[Any]] = [
        select(table).where(name_startswith(table, key)),
        select(group_table).where(name_startswith(group_table, key)),
    ]

    prefix_anchored = key.startswith("@")
    slash = key.find("/")

    # Possible combinations:
    #   @/abc  explicit non-expression of parent, anchored child; child = abc%
    #   @abc/  explicit expression of exact parent (trailing slash) parent = abc
    #   @abc   explicit expression of only the parent (no slash). parent = abc%
    #   @ab/cd explicit parent + child. parent = ab, child = cd
    #   abc/   explicit parent; parent = abc%
    #   /abc   explicit child; child = %abc%
    #   ab/cd  child + parent

    if prefix_anchored:  # "@parent", "@par/", "@/child", ...
        if slash == 1:  # "@", "/", ... -> left-anchored child
            if len(key) == 2:  # reject "@/"
                raise ValueError(f"overly ambiguous term (no actual characters): {key}")
            # search for just the child part
            exact_candidates.insert(0, select(table).where(table.name == key[2:]))
            like_candidates.insert(0, select(table).where(name_startswith(table, key[2:])))

        elif slash == -1:  # @abc... no slash, just the parent
            exact_candidates.insert(0, select(group_table).where(group_table.name == key[1:]))
            like_candidates.insert(0, select(group_table).where(name_startswith(group_table, key[1:])))
        else:  # @sol/[something...] <- combo
            parent_part, child_part = key[1:slash], key[slash + 1:]
            if not child_part:  # @sol/
                exact_candidates = [select(group_table).where(group_table.name == parent_part)]
                like_candidates = []
            else:
                exact_candidates.append(select(table).join(group_table).where(and_(group_table.name == parent_part, table.name == child_part)))
                like_candidates.insert(0, select(table).join(group_table).where(and_(name_startswith(group_table, parent_part), name_startswith(table, child_part))))
                like_candidates.insert(0, select(table).join(group_table).where(and_(group_table.name == parent_part, name_startswith(table, child_part))))

    # otherwise if the parent isn't anchored, it can be a wildcard.
    elif slash == len(key) - 1:  # "foo/"
        parent_part = key[:-1]
        # This tells us there's a single slash and it's at the end of the name,
        # in which case we're going to treat it *first* as a group name.
        # We still fall back to trying it directly but only as a last resort;
        # there *are* player-named places with a '/' at the end ("Here No\/\/")
        # but let that query pay for itself, not the other way around.
        exact_candidates = [
            select(group_table).where(group_table.name == key),
            select(group_table).where(group_table.name == parent_part),
            select(table).where(table.name == key),
        ]
        like_candidates = [
            select(group_table).where(name_startswith(group_table, key)),
            select(group_table).where(name_startswith(group_table, parent_part)),
            select(table).where(name_startswith(table, parent_part)),
        ]

    elif slash > 0:  # "par/table", and we know it's not trailing /
        parent_part, _, child_part = key.partition("/")

        exact_candidates = [
            select(table).where(table.name == key),
            # don't try matching the group because no groups can currently contain '/'.
            select(table).join(group_table).where(and_(group_table.name == parent_part, table.name == child_part)),
        ]
        like_candidates = [
            select(table).where(name_startswith(table, key)),
            select(table).join(group_table).where(group_table.name == parent_part, name_startswith(table, child_part)),
            select(table).join(group_table).where(name_startswith(group_table, parent_part), table.name == child_part),
            select(table).join(group_table).where(name_startswith(group_table, parent_part), name_startswith(table, child_part)),
        ]

    elif slash <= 0:  # "/foo" or "foo" suggests only a child
        child_part = key[1:] if slash == 0 else key
        exact_candidates.insert(0, select(table).where(table.name == child_part))
        like_candidates.insert(0, select(table).where(name_startswith(table, child_part)))

    # If there's no slash, then our initial patterns will suffice.

    for stmt in exact_candidates + like_candidates:
        rows = session.execute(stmt.limit(10)).all()
        if len(rows) == 1:
            return rows[0][0]
        if len(rows) > 1:  # ambiguity/conflict
            models = [row[0] for row in rows]
            raise AmbiguityError(kind, key, models, key=lambda r: r.dbname())

    return None
