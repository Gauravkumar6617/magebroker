import pytest
from magebroker.constraints import parse_constraint, InvalidConstraint


# --- Caret -------------------------------------------------------------------

def test_caret():
    spec = parse_constraint("^103.0")
    assert "103.0.6" in spec
    assert "104.0.0" not in spec
    assert "102.9.9" not in spec


def test_caret_strict():
    spec = parse_constraint("^102.0")
    assert "102.5.0" in spec
    assert "103.0.0" not in spec
    assert "103.0.6" not in spec


def test_caret_zero_minor():
    """^0.3 must mean >=0.3.0,<0.4.0 (minor ceiling, not major ceiling)."""
    spec = parse_constraint("^0.3")
    assert "0.3.0" in spec
    assert "0.3.9" in spec
    assert "0.4.0" not in spec
    assert "1.0.0" not in spec


def test_caret_zero_minor_exact():
    spec = parse_constraint("^0.3.2")
    assert "0.3.2" in spec
    assert "0.3.9" in spec
    assert "0.4.0" not in spec


# --- Tilde -------------------------------------------------------------------

def test_tilde_patch():
    spec = parse_constraint("~8.1.0")
    assert "8.1.5" in spec
    assert "8.2.0" not in spec


def test_tilde_minor():
    spec = parse_constraint("~8.1")
    assert "8.5.0" in spec
    assert "9.0.0" not in spec


# --- OR constraint -----------------------------------------------------------

def test_or_constraint():
    spec = parse_constraint("~8.1.0 || ~8.2.0")
    assert "8.1.5" in spec
    assert "8.2.3" in spec
    assert "8.3.0" not in spec


# --- AND ranges (space-separated) --------------------------------------------

def test_and_range_space():
    spec = parse_constraint(">=8.1 <8.4")
    assert "8.1.0" in spec
    assert "8.3.9" in spec
    assert "8.4.0" not in spec
    assert "8.0.9" not in spec


def test_and_range_comma():
    spec = parse_constraint(">=8.1,<8.4")
    assert "8.1.0" in spec
    assert "8.3.0" in spec
    assert "8.4.0" not in spec


# --- Bare "=" must not corrupt ">=" ------------------------------------------

def test_bare_equals_maps_to_double_equals():
    spec = parse_constraint("=103.0.6")
    assert "103.0.6" in spec
    assert "103.0.7" not in spec


def test_gte_not_corrupted_by_equals_fix():
    """>=8.1 must stay >= (not turn into >==8.1 which was the old bug)."""
    spec = parse_constraint(">=8.1")
    assert "8.1.0" in spec
    assert "8.2.0" in spec
    assert "8.0.9" not in spec


def test_lte_not_corrupted():
    spec = parse_constraint("<=8.2")
    assert "8.2.0" in spec
    assert "8.3.0" not in spec


# --- Magento patch-version normalisation ------------------------------------

def test_patch_version_in_constraint():
    """Constraint '103.0.6-p3' should normalise to 103.0.6."""
    spec = parse_constraint("=103.0.6-p3")
    assert "103.0.6" in spec


def test_patch_version_in_check():
    """Checking '103.0.6-p3 in ^103.0' must work after normalisation."""
    spec = parse_constraint("^103.0")
    # The version string itself carries the patch label
    assert "103.0.6-p3" in spec


def test_patch_version_tilde():
    spec = parse_constraint("~103.0.6-p3")
    assert "103.0.6" in spec
    assert "103.0.8" in spec
    assert "103.1.0" not in spec


# --- Exact / wildcard --------------------------------------------------------

def test_exact():
    spec = parse_constraint("103.0.6")
    assert "103.0.6" in spec
    assert "103.0.7" not in spec


def test_wildcard():
    spec = parse_constraint("*")
    assert "1.2.3" in spec


# --- Unknown syntax raises instead of silently matching everything -----------

def test_unknown_syntax_raises():
    with pytest.raises(InvalidConstraint):
        parse_constraint("foobar")


def test_unknown_syntax_in_or_raises():
    with pytest.raises(InvalidConstraint):
        parse_constraint("^1.0 || ???")
