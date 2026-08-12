# ioc api workflow 

## Standard automatic scan
``` mermaid 
sequenceDiagram
    participant K@{ "type" : "control" } as Kubili
    participant E@{ "type" : "database" } as EPICS
    participant A as IOC API
    participant R as experiment
    Note right of R: State.READY
    Note right of A: RDP:AUTOMATIC_SCAN_COUNTDOWN = 0
    A-->>A: RDP:RUN_CMD = 1
    A-->>E: RDP:RUN_CMD = 0
    E->>A: RDP:SCAN_TYPE
    A-->A: `check_able_to_run()`
    A->>R: `apply_scan_settings()`
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
    R-->>A: `state_callback(State.FINISHED)`
    A-->>E: RDP:STATE
    loop Every second
        A-->>E: RDP:AUTOMATIC_SCAN_COUNTDOWN
        A-->>E: RDP:POLARISATION_ESTIMATE
    end
```

### Machine state: cannot run diagnostic
``` mermaid 
sequenceDiagram
    participant K@{ "type" : "control" } as Kubili
    participant E@{ "type" : "database" } as EPICS
    participant A as IOC API
    participant R as experiment
    Note right of R: State.READY
    Note right of A: RDP:AUTOMATIC_SCAN_COUNTDOWN = 0
    A-->>A: RDP:RUN_CMD = 1
    A-->>E: RDP:RUN_CMD = 0
    E->>A: RDP:SCAN_TYPE
    A-->A: `check_able_to_run()`
    Note right of A: able_to_run = False
    A-->>E: RDP:RUN_INIHIBIT_STATE
    E-->>K: RDP:RUN_INIHIBIT_STATE
    A-->>E: RDP:ERROR_MSG
    E-->>K: RDP:ERROR_MSG
    loop Every second
        A-->>E: RDP:AUTOMATIC_SCAN_COUNTDOWN
        A-->>E: RDP:POLARISATION_ESTIMATE
    end
```

### User initiated abort
``` mermaid 
sequenceDiagram
    actor U as User
    participant K@{ "type" : "control" } as Kubili
    participant E@{ "type" : "database" } as EPICS
    participant A as IOC API
    participant R as experiment
    activate R
    Note right of R: State.RUNNING
    loop Every second
        R->>R: `depolarise()`
        R-->>E: RDP:PROGRESS
        E-->>K: RDP:PROGRESS
    end
    U->>K: ABORT
    K->>E: RDP:ABORT_CMD = 1
    E-->>A: RDP:ABORT_CMD
    A-->E: RDP:ABORT_CMD = 0
    A->>R: request_abort()
    deactivate R
    Note right of R: State.ABORTED
    R-->>A: `state_callback(State.ABORTED)`
    A-->>E: RDP:STATE
    Note right of R: State.FINISHED
    R-->>A: `state_callback(State.FINISHED)`
    A-->>E: RDP:STATE
    loop Every second
        A-->>E: RDP:AUTOMATIC_SCAN_COUNTDOWN
        A-->>E: RDP:POLARISATION_ESTIMATE
    end
```

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
    A-->A: `check_able_to_run()`
    A->>R: `apply_scan_settings()`
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
    Note right of U: electron go fast
```
