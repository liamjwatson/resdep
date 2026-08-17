# `resdep` architecture
## Key information

- simpleGUI and resdepGUI are powered by PySide6 (python 
    wrapper for Qt)
- Kubili is plain Qt
- experiment communicates with BbB and BLMs via 
    [pyEPICS](https://pyepics.github.io/pyepics/pv.html) PVs

## Local operation (python on OPI)
```mermaid
graph LR
    subgraph GUIs
        A["simpleGUI"];
        B["resdepGUI"];
    end
    subgraph API
        C["_experiment_handlers"];
    end
    A & B --> C
    subgraph worker thread
        E["experiment"];
        subgraph extensible_classes
            F["epicsBPMs"];
            G["epicsBPMs"];
        end
        subgraph helper_classes
            H["_fitting"];
            I["_plotting"];
            J["_archiver"];
            L["_calculations"];
        end
    end
    C --> E
    E <-.-> T[("EPICS")]
    E <-.-> F & G
    E <-.-> H & I
    E <-.-> J & L
    click A "../GUIs/simpleGUI" "simpleGUI"
    click B "../GUIs/resdepGUI" "resdepGUI"
    click C "../helper_classes/_experiment_handlers" "experiment handlers"
    click E "../resdep" "resdep experiment"
    click F "../extensible_classes/epicsBPMs" "epicsBPMs"
    click G "../extensible_classes/epicsBPMs" "epicsBPMs"
    click H "../helper_classes/_fitting" "fitting"
    click I "../helper_classes/_plotting" "plotting"
    click J "../helper_classes/_archiver" "archiver"
    click L "../helper_classes/_calculations" "calculations"
    click T "https://docs.epics-controls.org/en/latest/index.html" "EPICS"
```
## Kubili operation (through IOC)
```mermaid
graph LR
    subgraph GUIs
        K["Kubili"];
    end
    subgraph API
        O["ioc_api"];
        R["_record_access"];
    end
    T[("EPICS")];
    K --> T
    T <-.-> R
    R <-.-> O
    subgraph worker thread
        E["experiment"];
        subgraph extensible_classes
            F["epicsBPMs"];
            G["epicsBPMs"];
        end
        subgraph helper_classes
            H["_fitting"];
            I["_plotting"];
            J["_archiver"];
            L["_calculations"];
        end
    end
    API --> E
    E <-.-> F & G
    E <-.-> H & I
    E <-.-> J & L
    E <-.-> T
    click K "../../user_guide/kubili" "kubili"
    click T "https://docs.epics-controls.org/en/latest/index.html" "EPICS"
    click O "../IOC/ioc_api" "IOC API"
    click R "../IOC/record_access" "Record Access"
    click E "../resdep" "resdep experiment"
    click F "../extensible_classes/epicsBPMs" "epicsBPMs"
    click G "../extensible_classes/epicsBPMs" "epicsBPMs"
    click H "../helper_classes/_fitting" "fitting"
    click I "../helper_classes/_plotting" "plotting"
    click J "../helper_classes/_archiver" "archiver"
    click L "../helper_classes/_calculations" "calculations"
```
