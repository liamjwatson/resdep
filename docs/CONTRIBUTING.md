# Contributing
I (Liam) will not be able to maintain this project as I am only at the 
Australian Synchrotron for a fixed term. It is hosted on both Bitbucket 
(internal) and Github. 

There are three branches: `master`, `develop` and `kubili-refactor`. `master` 
is comprised primarily of merge commits from `develop`. `kubili-refactor` is, 
by its namesake, a refactor of some of the architecture and functionality of 
`resdep` to be closer to what is required for installation on an IOC 
with control from Kubili through `SR00RDP:` PVs (rather than the standard 
local communication between the `PySide6` `simple`/`resdepGUI` and the 
threaded worker function).

!!! Warning

    The `kubili-refactor` branch should be kept separate from `master` and 
    `develop` as it is currently untested for local operation. 
    While I have tried my best, some critical components of the local operation 
    may have broken during the refactor. I do not recommend merging this branch 
    into `develop` or `master`.

# Kubili
In the end, the GUI is to be designed and implemented into the current Kubili 
control system. As such, this repo may become redundant, as pushing to it may 
not result in implemented changes. I advise contacting the controls team.

# New builds for OPI
Since the control OPI do not have access to PyPI, they require a wheel and 
tarball distribution. If you make any new changes to the code base and want 
to update the install version on the OPIs, you must create new distribution 
files, you cannot install from source directly.

First, it is good practice to update the build version in `pyproject.toml`:

```toml title="pyproject.toml" hl_lines="3"
    [project]
    name = "resdep"
    version = "2.0.2"
    description = "Resonant depolarisation package for the Australian Synchrotron displayed in a Qt GUI front end using python backend tools piped through EPICS."
```

To create a new wheel (`.whl`) and tarball (`.tar.gz`), 
navigate the the project root and then **run**:

```bash hl_lines="1"
    $ uv build
    Building source distribution...
    Building wheel from source distribution...
    Successfully built dist/resdep-2.0.2.tar.gz
    Successfully built dist/resdep-2.0.2-py3-none-any.whl
```

!!! Warning

    If you are using the default `git` configuration, it is likely that it has 
    created a `.gitignore` in the `dist/` directory. If you want to push the new 
    distribution files to bitbucket so that you can clone them on the OPI, then 
    you will need to delete the `.gitignore` before push. FYI it's a hidden 
    file.

Installing the new build on the OPI should be as easy as following the 
[getting started](./getting_started.md) instructions, making sure you are in 
fact cloning your new commit.
