import pytest
import re

# arrange
@pytest.fixture
def first_test_str():
    return "11A"

# arrange
@pytest.fixture
def second_test_str():
    return "11B"

# arrange
@pytest.fixture
def remove_A_and_B_from_str(second_test_str):
    second_test_str = re.sub(pattern=r"A*|B*", repl="", string=second_test_str)
    return second_test_str


def test_re_removal(remove_A_and_B_from_str):
    # assert
    assert remove_A_and_B_from_str == "11"