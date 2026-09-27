from magebroker.constraints import parse_constraint


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


def test_tilde_patch():
    spec = parse_constraint("~8.1.0")
    assert "8.1.5" in spec
    assert "8.2.0" not in spec


def test_tilde_minor():
    spec = parse_constraint("~8.1")
    assert "8.5.0" in spec
    assert "9.0.0" not in spec


def test_or_constraint():
    spec = parse_constraint("~8.1.0 || ~8.2.0")
    assert "8.1.5" in spec
    assert "8.2.3" in spec
    assert "8.3.0" not in spec


def test_exact():
    spec = parse_constraint("103.0.6")
    assert "103.0.6" in spec
    assert "103.0.7" not in spec


def test_wildcard():
    spec = parse_constraint("*")
    assert "1.2.3" in spec
