import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from tradedangerous.db import search
from tradedangerous.db.orm_models import Base, Category, Item
from tradedangerous.tradeexcept import AmbiguityError


# -----------------------------------------------------------------------------
# Test Data

# Mock category data: (category_id, name)
MOCK_CATEGORIES = [
    (1, "Metals"),
    (2, "Minerals"),
    (3, "Chemicals"),
    (4, "Foods"),
    (5, "Misc"),
]

# Mock item data: (item_id, name, category_id, ui_order, avg_price, fdev_id)
MOCK_ITEMS = [
    (100, "Platinum", 1, 0, 0, 100),
    (101, "Gold", 1, 0, 0, 101),
    (102, "Gold Pressed Latinum", 1, 0, 0, 102),
    (103, "Bertrandite", 2, 0, 0, 103),
    (104, "Fruit and Vegetables", 4, 0, 0, 104),
    (105, "Food Cartridges", 4, 0, 0, 105),
    (106, "Non-Lethal Weapons", 5, 0, 0, 106),
    (107, "H.E. Suits", 5, 0, 0, 107),
    (108, "Agri-Medicines", 5, 0, 0, 108),
    (109, "Baltah'sine Vacuum Krill", 5, 0, 0, 109),
]


@pytest.fixture
def test_session() -> Session:
    """Create an in-memory SQLite session with test Category and Item data.
    
    Uses MOCK_CATEGORIES and MOCK_ITEMS constants to populate the database.
    """
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()
    
    # Populate from MOCK_CATEGORIES
    for cat_id, name in MOCK_CATEGORIES:
        session.add(Category(category_id=cat_id, name=name))
    session.flush()
    
    # Populate from MOCK_ITEMS
    for item_id, name, category_id, ui_order, avg_price, fdev_id in MOCK_ITEMS:
        session.add(Item(
            item_id=item_id,
            name=name,
            category_id=category_id,
            ui_order=ui_order,
            avg_price=avg_price,
            fdev_id=fdev_id
        ))
    session.commit()
    
    yield session
    session.close()


# -----------------------------------------------------------------------------
# PUNCT_REGEX test

def test_PUNCT_REGEX() -> None:
    """Test that PUNCT_REGEX correctly strips punctuation and whitespace."""
    assert search.PUNCT_REGEX.sub("", "") == ""
    assert search.PUNCT_REGEX.sub("", "normalstring") == "normalstring"
    assert search.PUNCT_REGEX.sub("", """/.,;:'"?!++-""") == ""
    assert search.PUNCT_REGEX.sub("", "Hello, world!") == "Helloworld"


# -----------------------------------------------------------------------------
# escaped_for_like validation

@pytest.mark.parametrize("input_str,expected", [
    ("", ""),
    ("normalstring", "normalstring"),
    ("abc 123 ~`!@#$^&*()-+=[]{};:/", "abc 123 ~`!@#$^&*()-+=[]{};:/"),
])
def test_escaped_for_like_normal_chars(input_str: str, expected: str) -> None:
    """Test that non-special characters pass through unchanged."""
    assert search.escaped_for_like(input_str) == expected


@pytest.mark.parametrize("input_str,expected", [
    ("%", r"\%"),
    ("_", r"\_"),
    ("\\", "\\\\"),
    ("50%", "50\\%"),
    ("test_item", "test\\_item"),
    ("path\\to\\file", "path\\\\to\\\\file"),
    (r"\\\%\_\ ", r"\\\\\\\%\\\_\\ "),
])
def test_escaped_for_like_special_chars(input_str: str, expected: str) -> None:
    """Test that SQL LIKE special characters ('%', '_', '\\') are properly escaped."""
    assert search.escaped_for_like(input_str) == expected


# -----------------------------------------------------------------------------
# needle_from_term tests

@pytest.mark.parametrize("bad_value", [
    "",
    "@",
    "/",
    "@/",
])
def test_needle_from_term_empty_raises(bad_value: str) -> None:
    """Test that empty search terms raise appropriate ValueError."""
    with pytest.raises(ValueError) as excinfo:
        search.needle_from_term(bad_value)
    assert str(excinfo.value) == "empty field"


@pytest.mark.parametrize("bad_value", ["@a", "a/", "@a/"])
def test_needle_from_term_single_char_raises(bad_value: str) -> None:
    """Test that single-character searches raise 'overly ambiguous' ValueError."""
    with pytest.raises(ValueError) as excinfo:
        search.needle_from_term(bad_value)
    assert str(excinfo.value) == f"overly ambiguous field: '{bad_value}'"


def test_needle_from_term_too_long_raises() -> None:
    """Test that terms exceeding NAME_LENGTH raise ValueError."""
    long_term = "a" * (search.NAME_LENGTH + 1)
    with pytest.raises(ValueError) as excinfo:
        search.needle_from_term(long_term)
    assert f"limited to {search.NAME_LENGTH}" in str(excinfo.value).lower()
    assert str(search.NAME_LENGTH) in str(excinfo.value)


def test_needle_from_term_escapes_special_chars() -> None:
    """Test that needle patterns escape SQL special chars before building pattern."""
    needle = search.needle_from_term("abc")
    assert needle.pattern == "%a%b%c%"

    needle = search.needle_from_term("%\\_")
    assert needle.pattern == "%\\%%\\\\%\\_%"


@pytest.mark.parametrize("term,normalized,pattern,left_anchor,right_anchor", [
    ("SOL", "sol", "%s%o%l%", False, False),
    ("@sOl", "sol", "s%o%l%", True, False),
    ("sOl/", "sol", "%s%o%l", False, True),
    ("@sOl/", "sol", "s%o%l", True, True),
    ("G-M:T,A", "gmta", "%g%m%t%a%", False, False),
])
def test_needle_from_term_valid(
    term: str,
    normalized: str,
    pattern: str,
    left_anchor: bool,
    right_anchor: bool
) -> None:
    """Test valid needle_from_term cases with various anchor combinations."""
    n = search.needle_from_term(term)
    assert n.normalized == normalized
    assert n.pattern == pattern
    assert n.left_anchored == left_anchor
    assert n.right_anchored == right_anchor


def test_needle_from_term_max_length_boundary() -> None:
    """Verify MAX_NAME_LENGTH boundary behavior (39, 40, 41 characters)."""
    # One below limit should work
    term_39 = "a" * (search.NAME_LENGTH - 1)
    n = search.needle_from_term(term_39)
    assert n.normalized == term_39.lower()
    
    # Exactly at limit should work
    term_40 = "a" * search.NAME_LENGTH
    n = search.needle_from_term(term_40)
    assert n.normalized == term_40.lower()
    
    # One above limit should fail
    term_41 = "a" * (search.NAME_LENGTH + 1)
    with pytest.raises(ValueError) as excinfo:
        search.needle_from_term(term_41)
    assert f"limited to {search.NAME_LENGTH}" in str(excinfo.value).lower()


# -----------------------------------------------------------------------------
# fuzzy_like tests

class TestFuzzyLike:
    """Test the fuzzy_like function with multi-tier matching."""
    
    def test_exact_match(self, test_session: Session) -> None:
        """Exact match should return the single item (bucket 1 priority)."""
        result = search.fuzzy_like(test_session, "Item", "Platinum", Item)
        assert result is not None
        assert result.item_id == 100
        assert result.name == "Platinum"
    
    def test_prefix_match(self, test_session: Session) -> None:
        """Prefix match should find unique item starting with prefix (bucket 2)."""
        result = search.fuzzy_like(test_session, "Item", "Plat", Item)
        assert result is not None
        assert result.item_id == 100
        assert result.name == "Platinum"
    
    def test_contains_match(self, test_session: Session) -> None:
        """Contains match should find item with characters in sequence (bucket 3)."""
        result = search.fuzzy_like(test_session, "Item", "gold p", Item)
        assert result is not None
        assert result.item_id == 102
        assert result.name == "Gold Pressed Latinum"
    
    def test_fuzzy_match_punctuation_normalized(self, test_session: Session) -> None:
        """Punctuation should be stripped during fuzzy matching (bucket 4)."""
        # Search for "baltah sine" should match "Baltah'sine Vacuum Krill"
        result = search.fuzzy_like(test_session, "Item", "baltah sine", Item)
        assert result is not None
        assert result.item_id == 109
    
    @pytest.mark.parametrize("search_term", ["go", "gol"])
    def test_ambiguous_prefix(self, test_session: Session, search_term: str) -> None:
        """Multiple prefix matches should raise AmbiguityError."""
        with pytest.raises(AmbiguityError) as excinfo:
            search.fuzzy_like(test_session, "Item", search_term, Item)
        assert search_term in str(excinfo.value).lower()
    
    def test_no_match(self, test_session: Session) -> None:
        """No matching characters should return None."""
        result = search.fuzzy_like(test_session, "Item", "xyz", Item)
        assert result is None
    
    def test_with_category_parent(self, test_session: Session) -> None:
        """Fuzzy match with parent category join should work."""
        result = search.fuzzy_like(test_session, "Item", "plat", Item, Category)
        assert result is not None
        assert result.item_id == 100
        assert result.name == "Platinum"
    
    def test_exact_wins_over_prefix(self, test_session: Session) -> None:
        """Exact matches (bucket 1) should win over prefix matches (bucket 2)."""
        # "Gold" is exact, so it should win over "Gold Pressed Latinum" prefix
        result = search.fuzzy_like(test_session, "Item", "gold", Item)
        assert result is not None
        assert result.item_id == 101
        assert result.name == "Gold"
    
    def test_prefix_wins_over_contains(self, test_session: Session) -> None:
        """Prefix matches (bucket 2) should win over contains matches (bucket 3)."""
        result = search.fuzzy_like(test_session, "Item", "plat", Item)
        assert result is not None
        assert result.item_id == 100
        assert result.name == "Platinum"


# -----------------------------------------------------------------------------
# fast_find tests

class TestFastFind:
    """Test the fast_find function for single-table searches."""
    
    def test_exact_match(self, test_session: Session) -> None:
        """Exact match should return the item."""
        result = search.fast_find(test_session, "Item", "Platinum", Item)
        assert result is not None
        assert result.item_id == 100
    
    def test_prefix_match(self, test_session: Session) -> None:
        """Unique prefix match should return the item."""
        result = search.fast_find(test_session, "Item", "Plat", Item)
        assert result is not None
        assert result.item_id == 100
    
    def test_ambiguous_prefix(self, test_session: Session) -> None:
        """Multiple prefix matches should raise AmbiguityError."""
        with pytest.raises(AmbiguityError) as excinfo:
            search.fast_find(test_session, "Item", "Go", Item)
        assert "Go" in str(excinfo.value)
    
    def test_no_match(self, test_session: Session) -> None:
        """No matching item should return None."""
        result = search.fast_find(test_session, "Item", "Nonexistent", Item)
        assert result is None
    
    def test_short_key_raises(self, test_session: Session) -> None:
        """Key shorter than 2 characters should raise ValueError."""
        with pytest.raises(ValueError) as excinfo:
            search.fast_find(test_session, "Item", "P", Item)
        assert "overly ambiguous" in str(excinfo.value)


# -----------------------------------------------------------------------------
# fast_find_sub tests

class TestFastFindSub:
    """Test the fast_find_sub function for parent/child hierarchical searches."""
    
    def test_exact_child_match(self, test_session: Session) -> None:
        """Exact child match should return the item."""
        result = search.fast_find_sub(test_session, "Item", "Platinum", Item, Category)
        assert result is not None
        assert result.item_id == 100
    
    def test_exact_parent_match(self, test_session: Session) -> None:
        """Exact parent match should return the category."""
        result = search.fast_find_sub(test_session, "Category", "Metals", Item, Category)
        assert result is not None
        assert result.category_id == 1
    
    def test_parent_slash_child(self, test_session: Session) -> None:
        """Format 'Parent/Child' should find the child item."""
        result = search.fast_find_sub(test_session, "Item", "Metals/Gold", Item, Category)
        assert result is not None
        assert result.item_id == 101
        assert result.name == "Gold"
    
    def test_parent_trailing_slash(self, test_session: Session) -> None:
        """Trailing slash format 'Parent/' should find the parent category."""
        result = search.fast_find_sub(test_session, "Category", "Metals/", Item, Category)
        assert result is not None
        assert result.category_id == 1
    
    def test_anchor_parent_only(self, test_session: Session) -> None:
        """Anchor '@Parent' should find the parent category."""
        result = search.fast_find_sub(test_session, "Category", "@Metals", Item, Category)
        assert result is not None
        assert result.category_id == 1
    
    def test_anchor_child_only(self, test_session: Session) -> None:
        """Anchor '@/Child' should find the child item."""
        result = search.fast_find_sub(test_session, "Item", "@/Platinum", Item, Category)
        assert result is not None
        assert result.item_id == 100
    
    def test_anchor_parent_child(self, test_session: Session) -> None:
        """Anchor '@Parent/Child' should find the child item."""
        result = search.fast_find_sub(test_session, "Item", "@Metals/Gold", Item, Category)
        assert result is not None
        assert result.item_id == 101
    
    def test_leading_slash_child_search(self, test_session: Session) -> None:
        """Leading slash '/Child' should search only children."""
        result = search.fast_find_sub(test_session, "Item", "/Platinum", Item, Category)
        assert result is not None
        assert result.item_id == 100
    
    def test_short_key_raises(self, test_session: Session) -> None:
        """Key shorter than 2 characters should raise ValueError."""
        with pytest.raises(ValueError) as excinfo:
            search.fast_find_sub(test_session, "Item", "A", Item, Category)
        assert "overly ambiguous" in str(excinfo.value)
    
    def test_empty_anchor_raises(self, test_session: Session) -> None:
        """Empty anchor format '@/' should raise ValueError."""
        with pytest.raises(ValueError) as excinfo:
            search.fast_find_sub(test_session, "Item", "@/", Item, Category)
        assert "no actual characters" in str(excinfo.value)
