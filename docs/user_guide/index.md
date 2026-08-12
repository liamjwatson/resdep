# Overview
`resdep` is a diagnostic tool to non-destructively measure the energy of the 
stored beam. For most use cases, this diagnostic simply runs in the background 
and periodically measures the beam energy, intelligently decided when to run 
and when to switch off. For this purpose, the [`Kubili`](kubili.md) or 
[`simpleGUI`](simpleGUI.md) are most appropriate points of control. 

If you want to do anything specific,[`resdepGUI`](resdepGUI.md) allows for 
control over many of the experimental parameters, and provides more high-level 
feedback.


The main 
difference being that Kubili controls the diagnostic running on an IOC which 
communicates through EPICS, whereas simpleGUI and resdepGUI are run locally on 
the OPIs and do not talk to `SR00RDP:$VAR` type PVs.


# [SimpleGUI](simpleGUI.md)
A simple Qt GUI for automatic monitoring of the beam energy, with some manual 
scan capabilities.

# [ResdepGUI](resdepGUI.md)
An expert level GUI for launching custom scans. Allows modification of most 
experiment parameters and features live plotting feedback.

# [Kubili](kubili.md)
In progress. See [JIRA ticket](https://jira.synchrotron.org.au/browse/ACC-1850).
