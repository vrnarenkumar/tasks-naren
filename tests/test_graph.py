import pandas as pd
import pytest
from graph import (
    classify_message,
    extract_known_id,
    is_unsupported,
    looks_like_id,
    to_lc_messages,
)
from langchain_core.messages import AIMessage, HumanMessage
from parts_catalog import PartsCatalog


@pytest.fixture
def catalog():
    df = pd.DataFrame(
        {
            "ID": ["A1", "A253"],
            "DESCRIPTION": [
                "Indicator Red Fast Movement 1.6A 250V Ceramic",
                "Indicator Red Fast Movement 1.6A 250V Ceramic Bulk",
            ],
            "Rated Current (A)": ["1.6A", "1.6A"],
        }
    )
    return PartsCatalog(df)


@pytest.fixture
def classify_catalog():
    # A2 shares no vocabulary with A1/A3, so it deliberately produces a
    # low-confidence "alternative" for A1 (same Rated Current, unrelated text)
    df = pd.DataFrame(
        {
            "ID": ["A1", "A2", "A3"],
            "DESCRIPTION": [
                "Indicator Red Fast Movement 1.6A 250V Ceramic",
                "Completely unrelated widget xylophone zephyr quokka",
                "Indicator Red Fast Movement 1.6A 250V Ceramic Bulk",
            ],
            "Rated Current (A)": ["1.6A", "1.6A", "6.3A"],
        }
    )
    return PartsCatalog(df)


def test_extract_known_id_finds_id_case_insensitively(catalog):
    assert extract_known_id("alternatives for a1?", catalog) == "A1"


def test_extract_known_id_returns_correct_casing(catalog):
    assert extract_known_id("A253 please", catalog) == "A253"


def test_extract_known_id_returns_none_when_absent(catalog):
    assert extract_known_id("any relevant parts with fuse?", catalog) is None


def test_extract_known_id_does_not_match_ordinary_words(catalog):
    # "fuse" shouldn't be mistaken for an ID just because it's part-related
    assert extract_known_id("how many fuses are in stock?", catalog) is None


@pytest.mark.parametrize(
    "message",
    [
        "how many fuses are in stock?",
        "what is the price?",
        "check availability",
        "STOCK levels please",
    ],
)
def test_is_unsupported_matches_business_keywords(message):
    assert is_unsupported(message) is True


@pytest.mark.parametrize(
    "message",
    ["ceramic fuse", "alternatives for A1", "what is a fuse?", "hello"],
)
def test_is_unsupported_false_for_catalog_and_general_messages(message):
    assert is_unsupported(message) is False


@pytest.mark.parametrize("message", ["ABC999", "A1", "xyz123"])
def test_looks_like_id_true_for_id_shaped_tokens(message):
    assert looks_like_id(message) is True


@pytest.mark.parametrize(
    "message",
    ["what is a fuse?", "hello", "ceramic fuse", "how are you"],
)
def test_looks_like_id_false_for_natural_language(message):
    assert looks_like_id(message) is False


def test_classify_message_unsupported(classify_catalog):
    label, result = classify_message("how many in stock?", classify_catalog)
    assert label == "unsupported"
    assert result is None


def test_classify_message_catalog_exact_id(catalog):
    label, result = classify_message("alternatives for A1", catalog)
    assert label == "catalog_exact_id"
    assert result["query_id"] == "A1"


def test_classify_message_low_confidence_for_weak_exact_id_match(classify_catalog):
    label, result = classify_message("A1", classify_catalog)
    assert label == "low_confidence"
    assert result["query_id"] == "A1"


def test_classify_message_catalog_search(classify_catalog):
    label, result = classify_message("Ceramic Bulk", classify_catalog)
    assert label == "catalog_search"
    assert result["matches"][0]["id"] == "A3"


def test_classify_message_not_found_for_unknown_id_shaped_text(classify_catalog):
    label, result = classify_message("ZZZ999", classify_catalog)
    assert label == "not_found"
    assert result is None


def test_classify_message_general_for_natural_language(classify_catalog):
    label, result = classify_message("what is a fuse?", classify_catalog)
    assert label == "general"
    assert result is None


def test_to_lc_messages_converts_roles_correctly():
    history = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    messages = to_lc_messages(history)

    assert isinstance(messages[0], HumanMessage)
    assert messages[0].content == "hi"
    assert isinstance(messages[1], AIMessage)
    assert messages[1].content == "hello"
