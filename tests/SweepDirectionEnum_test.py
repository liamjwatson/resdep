from resdep.experiment import SweepDirection

def test_enum_value():
    assert SweepDirection.BACKWARD == -1
    assert SweepDirection.FORWARD == 1
