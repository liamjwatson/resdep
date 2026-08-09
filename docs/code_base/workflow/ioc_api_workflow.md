# ioc api workflow 

## Standard automatic scan
``` mermaid 
sequenceDiagram
    participant K@{ "type" : "control" } as Kubili
    participant E@{ "type" : "database" } as EPICS
    participant A as IOC API
    participant R as experiment
    Note right of R: State.READY
    K-->K: Automatic countdown -> 0
    K->>E: RDP:RUN_CMD = 1
    E->>A: RDP:RUN_CMD 
    A-->>E: RDP:RUN_CMD = 0
    E->>A: RDP:SCAN_TYPE
    A->>R: `apply_scan_settings()`
    A-->A: `check_able_to_run()`
    A->>R: `run_experiment()`
    activate R
    Note right of R: State.RUNNING
    loop Every second
        R->>R: `depolarise()`
        R-->>E: RDP:PROGRESS
        E-->>K: RDP:PROGRESS
    end
    R-->>E: RDP:BEAM_ENERGY
    E-->>K: RDP:BEAM_ENERGY
    deactivate R
    Note right of R: State.FINISHED
    R->>A: `state_callback(State.FINISHED)`
    loop Every second
        A-->>E: RDP:AUTOMATIC_SCAN_COUNTDOWN
        A-->>E: RDP:POLARISATION_ESTIMATE
    end
```

### Machine state: cannot run diagnostic

### User initiated abort

## Standard manual scan
``` mermaid 
sequenceDiagram
    actor U as User
    participant K@{ "type" : "control" } as Kubili
    participant E@{ "type" : "database" } as EPICS
    participant A as IOC API
    participant R as experiment
    Note right of R: State.READY
    U->>K: Click "run"
    K->>E: RDP:RUN_CMD = 1
    E->>A: RDP:RUN_CMD 
    A-->>E: RDP:RUN_CMD = 0
    E->>A: RDP:SCAN_TYPE
    A->>R: `apply_scan_settings()`
    A-->A: `check_able_to_run()`
    A->>R: `run_experiment()`
    activate R
    Note right of R: State.RUNNING
    loop Every second
        R->>R: `depolarise()`
        R-->>E: RDP:PROGRESS
        E-->>K: RDP:PROGRESS
    end
    R-->>E: RDP:BEAM_ENERGY
    E-->>K: RDP:BEAM_ENERGY
    deactivate R
    Note right of R: State.FINISHED
```
