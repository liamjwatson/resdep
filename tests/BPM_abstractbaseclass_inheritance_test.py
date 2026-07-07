import pytest

from resdep.epicsBPMs import BPMs

class TestBPMs(BPMs):
    def connect():
        pass
    
def test_inherit_without_defining_connect():
    with pytest.raises(TypeError):
        BPMs()
        

def test_if_has_PV_attrs(): 
    test_bpms = TestBPMs()

    assert hasattr(test_bpms, "x_position_PVs")

