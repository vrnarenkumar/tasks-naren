import pandas as pd
import pytest
from parts_catalog import PartsCatalog


@pytest.fixture
def catalog():
    df = pd.DataFrame(
        {
            "ID": ["A1", "A2", "A3", "A4", "A5"],
            "DESCRIPTION": [
                "Indicator Red Fast Movement 1.6A 250V Ceramic",
                "Indicator Red Fast Movement 1.6A 250V Ceramic Bulk",
                "Indicator Red Slow Blow Movement 6.3A 250V Ceramic",
                None,  # no description -> excluded from search/known_ids
                "Indicator Red Fast Movement Ceramic, current unspecified",
            ],
            "Rated Current (A)": ["1.6A", "1.6A", "6.3A", "2A", None],
        }
    )
    return PartsCatalog(df)


def test_known_ids_excludes_rows_without_description(catalog):
    assert catalog.known_ids() == {"A1", "A2", "A3", "A5"}


def test_find_alternatives_is_case_insensitive(catalog):
    result = catalog.find_alternatives("a1")
    assert result["query_id"] == "A1"


def test_find_alternatives_filters_by_rated_current(catalog):
    result = catalog.find_alternatives("A1")
    alternative_ids = [alt["id"] for alt in result["alternatives"]]
    assert "A2" in alternative_ids  # same 1.6A rating
    assert "A3" not in alternative_ids  # different rating (6.3A), filtered out


def test_find_alternatives_unknown_id_returns_no_alternatives(catalog):
    result = catalog.find_alternatives("ZZZ99")
    assert result["alternatives"] == []
    assert result["warnings"]


def test_find_alternatives_missing_rated_current_gets_warning(catalog):
    result = catalog.find_alternatives("A5")
    assert any("unverified" in warning for warning in result["warnings"])


def test_find_alternatives_respects_k(catalog):
    result = catalog.find_alternatives("A1", k=1)
    assert len(result["alternatives"]) <= 1


def test_search_by_text_ranks_best_match_first(catalog):
    result = catalog.search_by_text("Slow Blow 6.3A")
    assert result["matches"][0]["id"] == "A3"


def test_add_csv_text_adds_new_parts(catalog):
    csv_text = "ID;DESCRIPTION;Rated Current (A)\nB1;Brand new part;5A\n"
    added = catalog.add_csv_text(csv_text)
    assert added == 1
    assert "B1" in catalog.known_ids()


def test_add_csv_text_prefixes_colliding_ids(catalog):
    csv_text = "ID;DESCRIPTION;Rated Current (A)\nA1;Different part, same ID;5A\n"
    catalog.add_csv_text(csv_text, source_label="uploaded")
    assert "uploaded_A1" in catalog.known_ids()
    assert "A1" in catalog.known_ids()  # original untouched


def test_add_csv_text_missing_required_column_raises(catalog):
    csv_text = "ID;Rated Current (A)\nB1;5A\n"  # no DESCRIPTION column
    with pytest.raises(ValueError):
        catalog.add_csv_text(csv_text)


def test_copy_is_isolated_from_original(catalog):
    session_copy = catalog.copy()
    session_copy.add_csv_text("ID;DESCRIPTION;Rated Current (A)\nB1;New part;5A\n")

    assert "B1" in session_copy.known_ids()
    assert "B1" not in catalog.known_ids()
