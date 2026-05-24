## [Beam Loss Monitors (BLMs)](epicsBLMs.md)
Class that connects to BLM PVs, grabs inital values and restores defaults.

## [Beam Position Monitors (BPMs)](epicsBPMs.md)
Collection of subclasses for each group of BPMs (
    [storage ring](./epicsBPMs.md#resdep.epicsBPMs.SR_BPMs), 
    [MX3](./epicsBPMs.md#resdep.epicsBPMs.MX3_BPMs), 
    [TBPMs](./epicsBPMs.md#resdep.epicsBPMs.TBPMs) 
). 
Subclasses inherit from abstract base class [BPMs](./epicsBPMs.md#resdep.epicsBPMs.BPMs), similar to [Accelerator Middle Layer](https://python-accelerator-middle-layer.github.io/) works.