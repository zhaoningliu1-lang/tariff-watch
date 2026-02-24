"""Tests for normalize.py"""

import pandas as pd
import pytest

from tariff_watch.normalize import normalize_hts_code, parse_rate, clean_description, normalize_dataframe


def test_hts_code_strips_dots():
    assert normalize_hts_code("8471.30.00.00") == "8471300000"


def test_hts_code_strips_spaces():
    assert normalize_hts_code("8471 30 0000") == "8471300000"


def test_hts_code_none():
    assert normalize_hts_code(None) is None


def test_parse_rate_free():
    assert parse_rate("Free") == 0.0
    assert parse_rate("FREE") == 0.0
    assert parse_rate("free") == 0.0


def test_parse_rate_percent():
    assert parse_rate("5%") == 5.0
    assert parse_rate("12.5%") == 12.5


def test_parse_rate_none_for_unknown():
    result = parse_rate("Special compound rate")
    assert result is None


def test_parse_rate_none_input():
    assert parse_rate(None) is None


def test_clean_description():
    assert clean_description("  foo   bar  ") == "foo bar"
    assert clean_description(None) is None


def test_normalize_dataframe():
    df = pd.DataFrame(
        {
            "hts_code": ["8471.30.00.00", "8542.31.00.00"],
            "description": ["  Portable machines  ", "Integrated circuits"],
            "rate_general_raw": ["Free", "5%"],
            "rate_special_raw": ["Free", "Free"],
            "rate_column2_raw": ["35%", "35%"],
        }
    )
    result = normalize_dataframe(df)
    assert result.loc[0, "hts_code"] == "8471300000"
    assert result.loc[0, "rate_general_value"] == 0.0
    assert result.loc[1, "rate_general_value"] == 5.0
    assert result.loc[0, "description"] == "Portable machines"
