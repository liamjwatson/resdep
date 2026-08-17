## [Architecture](./architecture.md)
Arhitecture of the `resdep` software package. How each module fits in to 
each other.
## [Workflow](./workflow/index.md)
Step-by-step explanation of how the resonant depolarisation runs, which 
functions are called and in what order.

## [GUIs](./GUIs/index.md)
Graphical user interfaces (GUIs) written in Qt 
(but which are not Kubili - see 
[SOP](https://confluence.synchrotron.org.au/confluence/pages/viewpage.action?pageId=444268831)
for control.)

Two options
- [`simpleGUI`](./GUIs/simpleGUI.md): standard operation
- [`resdepGUI`](./GUIs/resdepGUI.md): expert use (machine studies)

## [Helper classes](./helper_classes/index.md)
Helper classes for the resonant depolarisation experiment (
    [accessing the archiver](./helper_classes/_archiver.md),
    [calculations](./helper_classes/_calculations.md),
    [fitting](./helper_classes/_fitting.md),
    [plotting](./helper_classes/_plotting.md) 
).

## [Extensible classes](./extensible_classes/index.md)
Classes that can be easily used as-is, applied to new projects without 
modification, and are written in a easily extensible way to add new functions 
or subclasses. 

## [IOC](./IOC/index.md)
IOC functionality (API, EPICS record access etc)
