# triton-lang/triton

- Local path: `D:\vbox\repos\oss-issue-fixer-agent\.work\triton-lang__triton`
- Top-level dirs: `bin, cmake, docs, examples, include, lib, python, scripts, test, third_party, unittest, utils`
- Dev docs: `docs, CONTRIBUTING.md, AGENTS.md`

## README Excerpt

```text

| **`Documentation`** | **`Nightly Wheels`** |
|-------------------- | -------------------- |
| [![Documentation](https://github.com/triton-lang/triton/actions/workflows/documentation.yml/badge.svg)](https://triton-lang.org/) | [![Wheels](https://github.com/triton-lang/triton/actions/workflows/wheels.yml/badge.svg)](https://github.com/triton-lang/triton/actions/workflows/wheels.yml) |

# Triton Conference 2025

![Triton Banner](https://github.com/user-attachments/assets/b4b6972a-857c-417f-bf2c-f16f38a358c0)

The 3rd Triton Developer Conference took place on October 21, 2025 at the Microsoft Silicon Valley Campus in Mountain View, California.

### Conference Materials

Conference recordings and materials are now available online:

- **Conference Videos:** [YouTube Playlist](https://www.youtube.com/playlist?list=PLc_vA1r0qoiQqCdWFDUDqI90oY5EjfGuO)
- **Conference Slides:** [Google Drive Folder](https://drive.google.com/drive/folders/1KB6tD3UM1J0_eUp-F-JSlGrargLBawIr)

For previous conference materials, see:
- [2024 Conference Materials](docs/meetups/dev_conference_2024.md)
- [2023 Conference Materials](docs/meetups/dev-meetup-2023.md)

# Triton

This is the development repository of Triton, a language and compiler for writing highly efficient custom Deep-Learning primitives. The aim of Triton is to provide an open-source environment to write fast code at higher productivity than CUDA, but also with higher flexibility than other existing DSLs.

The foundations of this project are described in the following MAPL2019 publication: [Triton: An Intermediate Language and Compiler for Tiled Neural Network Computations](http://www.eecs.harvard.edu/~htk/publication/2019-mapl-tillet-kung-cox.pdf). Please consider citing this work if you use Triton!

The [official documentation](https://triton-lang.org) contains installation instructions and tutorials.  See also these third-party [Triton puzzles](https://github.com/srush/Triton-Puzzles), which can all be run using the Triton interpreter -- no GPU required.

# Quick Installation

You can install the latest stable release of Triton from pip:

```shell
pip install triton
```

Binary wheels are available for CPython 3.10-3.14.

# Install from source

```shell
git clone https://github.com/triton-lang/triton.git
cd triton

pip install -r python/requirements.txt # build-time dependencies
pip install -e .
```

Or with a virtualenv:

```shell
git clone https://github.com/triton-lang/triton.git
cd triton

python -m venv .venv --prompt triton
source .venv/bin/activate

pip install -r python/requirements.txt # build-time dependencies
pip install -e .
```

# Building with a custom LLVM

Triton uses LLVM to generate code for GPUs and CPUs.  Normally, the Triton build
downloads a prebuilt LLVM, but you can also build and use LLVM from source.

LLVM does not have a stable API, so the Triton build will not work at an
arbitrary LLVM version.

For convenience, use the following command to build LLVM and install Triton with the custom LLVM:

```shell
make dev-install-llvm
```

<details>
<summary>
Alternatively, follow these steps to build LLVM from source manually.
</summary>

1. Find the version of LLVM that Triton builds against.  Check
`cmake/llvm-hash.txt` to see the current version. For example, if it says:
       49af6502c6dcb4a7f7520178bd14df396f78240c.

   This means that the version of Triton you have builds against
   [LLVM](https://github.com/llvm/llvm-project) 49af6502.

2. `git checkout` LLVM at this revision.  Optionally, make additional
   modifications to LLVM.

3. [Build LLVM](https://llvm.org/docs/CMake.html).  For example, you might run:

       $ cd $HOME/llvm-project  # your clone of LLVM.
       $ mkdir build
       $ cd build
       $ cmake -G Ninja -DCMAKE_BUILD_TYPE=Release -DLLVM_ENABLE_ASSERTIONS=ON ../llvm -DLLVM_ENABLE_PROJECTS="mlir;llvm;lld" -DLLVM_TARGETS_TO_BUILD="host;NVPTX;AMDGPU"
       $ ninja

4. Grab a snack, this will take a while.

5. Build Triton as above, but set the following environment variables:

       # Modify as appropriate to point to your LLVM build.
       $ export LLVM_BUILD_DIR=$HOME/llvm-project/build

       $ cd <triton install>
       $ LLVM_INCLUDE_DIRS=$LLVM_BUILD_DIR/include \
         LLVM_LIBRARY_DIR=$LLVM_BUILD_DIR/lib \
         LLVM_SYSPATH=$LLVM_BUILD_DIR \
         pip install -e .

</details>

# Tips for building

- Set `TRITON_BUILD_WITH_CLANG_LLD=true` as an environment variable to use clang
  and lld.  lld in particular results in faster builds.

- Set `TRITON_BUILD_WITH_CCACHE=true` to build with ccache.

- Set `TRITON_HOME=/some/path` to change the location of the `.triton`
  directory where Triton's cache is located and downloads are stored
  during the build. By default, this is the user's home directory. It
  can be changed anytime.

- If you're running out of memory when building Triton, specify the `MAX_JOBS`
  environment variable (to the `pip install -e .` command) to limit the
  number of jobs.

- Pass `--no-build-isolation` to `pip install` to make nop builds faster.
  Without this, every invocation of `pip install` uses a different symlink to
  cmake, and this forces ninja to rebuild most of the `.a` files.

- The build system creates a `compile_commands.json` file under the Triton repo
  directory. This file is used by VSCode IntelliSense and clangd to provide
  code completion and other features for C++ code.

  If IntelliSense does not work, you can try the following steps:

    - Do a local build. Run command `pip install -e .`.
    - Get the full path to the `compile_commands.json` file produced by the build:
      `find ./build -name 'compile_commands.json' | xargs readlink -f`.
      You might get a full path similar to `/Users/{username}/triton/build/cmake.macosx-11.1-arm64-cpython-3.12/compile_commands.json`.
    - In VSCode, install the
      [C/C++
      extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode.cpptools),
      then open the command palette (`Shift + Command + P` on Mac, or `Shift +
      Ctrl + P` on Windows/Linux) and open `C/C++: Edit Configurations (UI)`.
    - Open "Advanced Settings" and paste the full path to
      `compile_commands.json` into the "Compile Commands" textbox.

# Running tests

There currently isn't a turnkey way to run all the Triton tests, but you can
follow the following recipe:

```shell
# One-time setup.  Note this will reinstall local Triton because torch
# overwrites it with the public version.
$ make dev-install

# To run all tests (requires a GPU)
$ make test

# Or, to run tests without a gpu
$ make test-nogpu
```

# Tips for hacking

For detailed instructions on how to debug Triton's frontend, please refer to this [tutorial](https://triton-lang.org/main/programming-guide/chapter-3/debugging.html). The following includes additional tips for hacking on Triton's backend.

**Configuration knobs**

See [`python/triton/knobs.py`](python/triton/knobs.py) for the full list of configuration knobs. You can set those knobs directly in python or use environment variables to control them. Below are some of the environment variables you can specify (see `knobs.py` for the full list):

- `MLIR_ENABLE_DUMP=1` dumps the IR before every MLIR pass Triton runs, for all
   kernels. Use `MLIR_ENABLE_DUMP=kernelName` to dump for a specific kernel only.
  - Triton cache can interfere with the dump. In cases where `MLIR_ENABLE_DUMP=1` does not work, try cleaning your triton cache: `rm -r ~/.triton/cache/*`.
- `MLIR_DUMP_PATH` specifies where `MLIR_ENABLE_DUMP` will dump to. If unset will dump to stderr.
- `LLVM_IR_ENABLE_DUMP=1` dumps the IR before every pass run over the LLVM IR.
- `TRITON_REPRODUCER_PATH=<reproducer_path>` will generate an MLIR reproducer file
  at `<reproducer_path>` before each MLIR compiler stage. If any of the stages fail,
  `<reproducer_path>` will be a local MLIR reproducer captured right before the failing pass.
- `TRITON_INTERPRET=1` uses the Triton interpreter instead of
```

## CONTRIBUTING Excerpt

```text
# Governance Structure

Triton adopts the following hierarchical technical governance structure:
* A community of **contributors** who file issues and submit pull requests
* A group of **module maintainers** who own parts of Triton and drive their development
* A body of **core maintainers** who own Triton overall and drive its development
* A **lead core maintainer** who is the catch-all decision maker when consensus cannot be reached by core maintainers

All contributions are expected to follow Triton’s design principles, as enforced by module and core maintainers. While high-quality pull requests are appreciated and encouraged, all maintainers reserve the right to prioritize their own work over code reviews at-will, hence contributors should not expect their work to be reviewed promptly.

Contributors can maximize the chances of their work being accepted by maintainers by meeting a high quality bar before sending a PR to maintainers.  We encourage maintainers who contribute to Triton on behalf of a company to get reviews from senior developers within their company before sending to maintainers.
Module maintainers
We aim to make the Triton codebase as modular as possible, such that different components (e.g., subdirectories) can be improved in parallel under the supervision of different module maintainers.

What constitutes (or not) a module is up to the core maintainers. Core maintainers also reserve the right to decide whether the development of a module should happen – or keep happening – in-tree or not.

**List of in-tree modules (as of 05/12/2024, alphabetical order):**
* AMD backend (Lei Zhang)
* Interpreter (Keren Zhou)
* Profiler (Keren Zhou)

Note: Parts of Triton that are not listed above (e.g., Nvidia backend) are assumed to be owned by core maintainers.

Note: Some important parts of the Triton eco-system (e.g., Intel XPU backend) may be maintained out-of-tree and advertised in our repository. The governance rules described in this document do not carry over to these modules.

__List of out-of-tree modules (as of 05/12/2024, alphabetical order):__
* CPU backend (Bert Maher, Ilya Enkovich)
* Intel backend (Ettore Tiotto, Whitney Tsang)


## Core maintainers
The core maintainers drive the development of Triton at large and set the roadmap for the project. As such, they have the following responsibilities:
* Proposing, implementing and reviewing profound changes to user-facing APIs, IR specifications and/or pass infrastructures
* Enforcing code quality standards and adherence to core design principles
* Drawing module boundaries and resolving disputes between module maintainers


The core maintainers as a group have the power to veto any decision made at a Module maintainer level.

The core maintainers should publicly articulate their decision-making, and share the reasoning behind their decisions, vetoes, and dispute resolution.

__List of core maintainers (as of 01/30/2025, alphabetical order):__
* Jeff Niu
* Keren Zhou
* Mario Lezcano-Casado
* Pawel Szczerbuk
* Peter Bell
* Phil Tillet
* Thomas Raoux
* Zahi Moudallal

## Lead core maintainer
When core maintainers cannot come to a consensus, a publicly declared lead maintainer is expected to settle the debate and make executive decisions.

The Lead Core Maintainer should publicly articulate their decision-making, and give a clear reasoning for their decisions.

The Lead Core Maintainer is also responsible for confirming or removing core maintainers.

**Lead maintainer (as of 05/12/2024)**
* Phil Tillet

# Decision Making

## Uncontroversial Changes

We are committed to accepting functional bug fixes that meet our quality standards – and include minimized unit tests to avoid future regressions. Performance improvements generally fall under the same category, with the caveat that they may be rejected if the trade-off between usefulness and complexity is deemed unfavorable by core maintainers (e.g., complex swizzling logic to improve the performance of non-tensor-cores matrix multiplications). Design changes that neither fix known functional nor performance issues are automatically considered controversial.

## Controversial Changes

More controversial design changes (e.g., changes in our IRs/APIs/Passes) are evaluated on a case-by-case basis under the subjective judgment of core maintainers. While it is possible for contributors to propose and land deep design changes upstream (see https://github.com/triton-lang/triton/pull/1305), the community should expect such occurrences to be relatively rare.

```
