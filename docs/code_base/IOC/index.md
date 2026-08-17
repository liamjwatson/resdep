# IOC
Most of the logic here is build off and around the magic of 
[pyDevSup](https://epics-modules.github.io/pyDevSup/).

## [IOC API](./ioc_api.md)
The API on the IOC that passes commands from Kubili to the worker thread, and 
progress updates and results from the worker thread back to Kubili.

## [EPICS record access](./record_access.md)
The python definition of EPICS records used by the API.
