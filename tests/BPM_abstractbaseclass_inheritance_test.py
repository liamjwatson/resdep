import pytest

from resdep.epicsBPMs import BPMs

class TestBPMs(BPMs):
    def connect():
        pass
    
def test_inherit_without_defining_connect():
    with pytest.raises(TypeError):
        BPMs()
        

def test_type_only_definitions_are_not_attrs(): 
    """
    If I have a class, in the init lives
    x_position_bpms : dict[str, list[float]]
    etcetera, but without any actual initialisation like = {},
    then it should fail hasattr
    """

    test_bpms = TestBPMs()

    assert not hasattr(test_bpms, "x_position_PVs")

