# 开源代码仓开发体验评估报告

| 仓库 | 编码风格是否有定义 | 代码检测是否支持 | 容器环境是否定义 | 容器环境本地可搭建 | 本地增量构建时间 | 本地代码检测时间 | 本地UT执行时间 | 代码检查规则数量 | 自动修复是否具备 | AI辅助代码检视是否支持 | PR执行时长平均值 | 单次PR资源CPU/NPU消耗量 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| vllm-project/vllm | 是 | 是 | 是 | 是 | N/A | N/A | N/A | 41 | 是 | 是 | 468.38s | CPU: 估算 55.60 core-min; NPU: N/A |
| Ascend/MindIE-SD | 否 | 是 | 是 | 否 | N/A | N/A | N/A | N/A | 否 | 否 | N/A | CPU: N/A; NPU: N/A |

## Markdown 改进建议总览

| 分类 | 数量 |
| --- | --- |
| execution_failure_needs_manual_triage | 2 |
| missing_dependency_step | 1 |
| environment_network_blocker | 1 |
| missing_code_check_docs | 1 |
| container_docs_not_self_contained | 1 |
| repository_script_issue | 1 |

## vllm-project/vllm

- 本地路径: `D:\vbox\repos\vllm_upstream`
- Markdown 扫描文件数: `481`
- Markdown 相关文件: .buildkite/performance-benchmarks/README.md；benchmarks/auto_tune/README.md；benchmarks/kernels/deepgemm/README.md；benchmarks/multi_turn/README.md；CODE_OF_CONDUCT.md；docs/benchmarking/cli.md；docs/benchmarking/dashboard.md；docs/benchmarking/sweeps.md；... (+208)
- 编码风格是否定义: 是
- 编码风格证据: .clang-format；pyproject.toml:tool.ruff；pyproject.toml:tool.mypy；pyproject.toml:tool.pytest
- 代码检测是否支持: 是
- 代码检测证据: .coveragerc；.github\workflows\pre-commit.yml:actionlint；.github\workflows\pre-commit.yml:markdownlint；.github\workflows\pre-commit.yml:mypy；.github\workflows\pre-commit.yml:pre-commit；.pre-commit-config.yaml；mypy；requirements/test.txt:coverage；... (+2)
- 自动修复是否具备: 是
- 自动修复证据: pyproject.toml formatter config
- 容器环境: 是 / 是 / `docker_build`
- 容器定义文件: docker/Dockerfile；docker/Dockerfile.cpu；docker/Dockerfile.nightly_torch；docker/Dockerfile.ppc64le；docker/Dockerfile.rocm；docker/Dockerfile.rocm_base；docker/Dockerfile.s390x；docker/Dockerfile.tpu；... (+2)
- 容器镜像线索: base-${TARGETARCH}；fetch_vllm_${REMOTE_VLLM}；grafana/grafana:latest；intel/deep-learning-essentials:2025.3.2-0-devel-ubuntu24.04；nvidia/cuda:${CUDA_VERSION}-base-ubuntu22.04；nvidia/cuda:${CUDA_VERSION}-devel-ubuntu20.04；nvidia/cuda:${CUDA_VERSION}-devel-ubuntu22.04；prom/prometheus:latest；... (+6)
- 容器准备命令: `docker build -f docker/Dockerfile -t repo-eval/vllm_upstream:latest .`
- 容器环境说明: container environment can be prepared locally
- 规则统计明细: pyproject.toml: 14 (explicit Ruff selectors)；.pre-commit-config.yaml: 27 (pre-commit hook count)
- 文档中的安装命令: benchmarks/kernels/deepgemm/README.md: uv pip install -e .；docs/benchmarking/cli.md: uv pip install xxhash cbor2；docs/contributing/ci/update_pytorch_version.md: uv pip install torch torchvision torchaudio \ --index-url https://download.pytorch.org/whl/test/cu128；docs/contributing/incremental_build.md: uv venv --python 3.12 --seed；docs/contributing/incremental_build.md: source .venv/bin/activate；docs/contributing/incremental_build.md: VLLM_USE_PRECOMPILED=1 uv pip install -U -e . --torch-backend=auto；docs/contributing/incremental_build.md: uv pip install -r requirements/build.txt --torch-backend=auto；docs/contributing/profiling.md: pip install snakeviz；... (+243)
- 文档中的构建命令: benchmarks/kernels/deepgemm/README.md: uv pip install -e .；docs/contributing/incremental_build.md: cmake --preset release；docs/contributing/incremental_build.md: cmake --build --preset release --target install；docs/contributing/incremental_build.md: bin             cmake_install.cmake      _deps                                machete_generation.log；docs/contributing/incremental_build.md: build.ninja     CPackConfig.cmake        detect_cuda_compute_capabilities.cu  marlin_generation.log；docs/contributing/incremental_build.md: _C.abi3.so      CPackSourceConfig.cmake  detect_cuda_version.cc               _moe_C.abi3.so；docs/contributing/README.md: VLLM_USE_PRECOMPILED=1 uv pip install -e .；docs/contributing/README.md: uv pip install -e . --no-build-isolation；... (+33)
- 文档中的测试命令: docs/contributing/incremental_build.md: CMakeCache.txt  ctest                    _flashmla_C.abi3.so                  moe_marlin_generation.log；docs/contributing/README.md: uv pip install pytest pytest-asyncio；docs/contributing/README.md: pytest tests/；docs/contributing/README.md: pytest -s -v tests/test_logger.py；docs/features/quantization/modelopt.md: pytest -q tests/quantization/test_modelopt.py；tests/evals/gpt_oss/README.md: pytest -s -v tests/evals/gpt_oss/test_gpqa_correctness.py \ --config-list-file=configs/models-h200.txt；tests/evals/gpt_oss/README.md: pytest -s -v tests/evals/gpt_oss/test_gpqa_correctness.py \ --config-list-file=configs/models-b200.txt；tests/evals/gsm8k/README.md: pytest -s -v tests/evals/gsm8k/test_gsm8k_correctness.py \ --config-list-file=configs/models-small.txt；... (+11)
- 文档中的代码检测命令: docs/contributing/README.md: uv pip install pre-commit；docs/contributing/README.md: pre-commit install；docs/contributing/README.md: pre-commit run     # runs on staged files；docs/contributing/README.md: pre-commit run -a  # runs on all files (short for --all-files)；docs/contributing/README.md: pre-commit run --hook-stage manual mypy-3.10；origin/main:AGENTS.md: pre-commit install；origin/main:AGENTS.md: pre-commit run；origin/main:AGENTS.md: pre-commit run --all-files；... (+7)
- 文档中的容器命令: docs/benchmarking/dashboard.md: docker run -it --entrypoint /bin/bash -v /data/huggingface:/root/.cache/huggingface -e HF_TOKEN=$HF_TOKEN -e ON_CPU=1 --shm-size=16g --name vllm-cpu-ci public.ecr.aws/q9t5s3a7/vllm-ci-test-repo:${VLLM_COMMIT}-${IMG_SUFFIX}；docs/contributing/dockerfile/dockerfile.md: docker run \ --rm \ --user "$(id -u):$(id -g)" \ --workdir /workspace \ --volume "$(pwd)":/workspace \ ghcr.io/patrickhoefler/dockerfilegraph:alpine \ --output png \ --dpi 200 \ --max-label-length 50 \ --filename docker/Dockerfile \ --legend；docs/deployment/frameworks/dify.md: docker compose up -d；docs/deployment/frameworks/open-webui.md: docker run -d \ --name open-webui \ -p 3000:8080 \ -v open-webui:/app/backend/data \ -e OPENAI_API_BASE_URL=http://0.0.0.0:8000/v1 \ --restart always \ ghcr.io/open-webui/open-webui:main；docs/deployment/nginx.md: docker build . -f Dockerfile.nginx --tag nginx-lb；docs/deployment/nginx.md: docker build -f docker/Dockerfile . --tag vllm；docs/deployment/nginx.md: docker build \ -f docker/Dockerfile . \ --tag vllm \ --build-arg http_proxy=$http_proxy \ --build-arg https_proxy=$https_proxy；docs/deployment/nginx.md: docker network create vllm_nginx；... (+101)
- 增量构建命令: `VLLM_USE_PRECOMPILED=1 /home/robell/.local/bin/uv pip install --python /mnt/d/vbox/repos/repo_dev_eval_agent/.work/docprobe/vllm/.venv/bin/python -e .` -> 超时
- 增量构建实际探测耗时: `N/A`
- 本地代码检测命令: `/mnt/d/vbox/repos/repo_dev_eval_agent/.work/docprobe/vllm/.venv/bin/pre-commit run -a` -> 失败
- 本地代码检测实际探测耗时: `11.70s`
- UT 命令: `/mnt/d/vbox/repos/repo_dev_eval_agent/.work/docprobe/vllm/.venv/bin/python -m pytest tests/v1/structured_output/test_backend_xgrammar.py -q` -> 失败
- UT 实际探测耗时: `5.98s`
- 增量构建失败摘要: `timeout after 3600s`
- 代码检测失败摘要: `[INFO] Installing environment for https://github.com/rhysd/actionlint. [INFO] Once installed this environment will be reused. [INFO] This may take a few minutes... An unexpected error has occurred: URLError: <urlopen error [SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1000)> Check the log at /home/robell/.cache/pre-commit/pre-commit.log`
- UT 失败摘要: `ImportError while loading conftest '/mnt/d/vbox/repos/vllm_upstream/tests/conftest.py'. tests/conftest.py:7: in <module>     from tblib import pickling_support E   ModuleNotFoundError: No module named 'tblib'`
- PR 指标平台 / 时间窗: `github` / 最近 `30` 天
- PR 采样数量 / Workflow 数量: `8` / `16`
- PR 执行时长: 平均 `468.38s` / 中位 `233.00s` / 最近一次 `20.00s`
- PR 资源消耗: CPU: 估算 55.60 core-min; NPU: N/A
- AI 代码检视证据: pr#37915 review by gemini-code-assist[bot]；pr#37234 review by gemini-code-assist[bot]；pr#37421 review by gemini-code-assist[bot]；pr#37706 review by gemini-code-assist[bot]；pr#37725 review by gemini-code-assist[bot]；pr#38011 review by gemini-code-assist[bot]；pr#37998 review by gemini-code-assist[bot]；pr#37082 review by gemini-code-assist[bot]
- PR 采集说明: collected from GitHub Actions and PR APIs within the last 30 days
- PR Run 证据: run:22335906128 BC Lint pull_request；run:22335906118 pre-commit pull_request；run:22335896176 BC Lint pull_request；run:22335896188 pre-commit pull_request；run:22335890061 pre-commit pull_request；run:22335890086 BC Lint pull_request；run:22335866651 BC Lint pull_request；run:22335866630 pre-commit pull_request；... (+8)
- 命令推断依据: container strategy: docker_build；container environment can be prepared locally；markdown scanned: 481 files；tests/ or pytest.ini detected；.pre-commit-config.yaml detected；documented build command: docs/contributing/README.md
- Markdown 改进建议:
  - [medium/mixed/execution_failure_needs_manual_triage] 构建 命令执行失败，需要继续区分是文档漂移还是仓库行为变化 | 证据: 构建 command: VLLM_USE_PRECOMPILED=1 /home/robell/.local/bin/uv pip install --python /mnt/d/vbox/repos/repo_dev_eval_agent/.work/docprobe/vllm/.venv/bin/python -e .；构建 status: timeout；构建 failure: timeout after 3600s | 建议: 复核文档示例、依赖锁定和仓库脚本是否一致，并为该命令补一条 CI 烟测。
  - [high/documentation/missing_dependency_step] 测试 示例命令缺少必要的依赖准备步骤 | 证据: 测试 command: /mnt/d/vbox/repos/repo_dev_eval_agent/.work/docprobe/vllm/.venv/bin/python -m pytest tests/v1/structured_output/test_backend_xgrammar.py -q；测试 status: failed；测试 failure: ImportError while loading conftest '/mnt/d/vbox/repos/vllm_upstream/tests/conftest.py'. tests/conftest.py:7: in <module>     from tblib import pickling_support E   ModuleNotFoundError: No module named 'tblib' | 建议: 补全构建、测试、代码检测前的依赖安装步骤，确保文档里的命令能在新环境直接跑通。
  - [medium/environment/environment_network_blocker] 代码检测 阶段受到网络、镜像源或外部站点波动影响 | 证据: 代码检测 command: /mnt/d/vbox/repos/repo_dev_eval_agent/.work/docprobe/vllm/.venv/bin/pre-commit run -a；代码检测 status: failed；代码检测 failure: [INFO] Installing environment for https://github.com/rhysd/actionlint. [INFO] Once installed this environment will be reused. [INFO] This may take a few minutes... An unexpected error has occurred: URLError: <urlopen error [SSL: UNEXPECTED_ | 建议: 在文档中补充代理、镜像源和重试建议，并在 CI 中缓存依赖、测试数据或 pre-commit hook 环境。

## Ascend/MindIE-SD

- 本地路径: `D:\vbox\repos\MindIE-SD`
- Markdown 扫描文件数: `43`
- Markdown 相关文件: docker/README.md；docs/developer_guide.md；examples/cache/README.md；examples/service/service.md；README.md；SECURITY.md；origin/master:README.md；origin/master:SECURITY.md；... (+4)
- 编码风格是否定义: 否
- 编码风格证据: N/A
- 代码检测是否支持: 是
- 代码检测证据: requirements.txt:pre-commit；tests\run_UT_test.sh:test-script；tests\run_test.sh:test-script
- 自动修复是否具备: 否
- 自动修复证据: N/A
- 容器环境: 是 / 否 / `docker_documented`
- 容器定义文件: docker/README.md
- 容器镜像线索: N/A
- 容器准备命令: `N/A`
- 容器环境说明: docker is documented, but no runnable container definition was found
- 容器环境阻塞: repository mentions Docker but does not provide a runnable Dockerfile, compose file, devcontainer, or workflow container image
- 规则统计明细: N/A
- 文档中的安装命令: docs/developer_guide.md: pip install -r requirements.txt；docs/developer_guide.md: pip install wheel；docs/developer_guide.md: pip install mindiesd-*.whl；docs/developer_guide.md: pip install -e .；docs/developer_guide.md: pip install -r MindIE-SD/requirements.txt；docs/developer_guide.md: pip install coverage；examples/cache/README.md: pip install -r requirements.txt；examples/service/service.md: pip install ray；... (+19)
- 文档中的构建命令: docs/developer_guide.md: python setup.py bdist_wheel；docs/developer_guide.md: pip install -e .；README.md: python setup.py bdist_wheel；SECURITY.md: make -j$(nproc)；SECURITY.md: sudo make install；SECURITY.md: cmake .. -USE_TCP_OPENSSL_LOAD=ON；SECURITY.md: make -j&(nproc)；origin/master:README.md: python setup.py bdist_wheel；... (+6)
- 文档中的测试命令: docs/developer_guide.md: bash run_test.sh；origin/master:docs/zh/developer_guide.md: bash run_test.sh
- 文档中的代码检测命令: N/A
- 文档中的容器命令: docs/developer_guide.md: docker run -it -d --net=host --shm-size=1g \ --name <container-name> \ --device=/dev/davinci_manager:rwm \ --device=/dev/hisi_hdc:rwm \ --device=/dev/devmm_svm:rwm \ --device=/dev/davinci0:rwm \ -v /usr/local/Ascend/driver:/usr/local/Ascend/driver:ro \ -v /usr/local/Ascend/firmware/:/usr/local/Ascend/firmware:ro \ -v /usr/local/sbin:/usr/local/sbin:ro \ -v /path-to-weights:/path-to-weights:ro \ mindie:2.2.RC1-800I-A2-py311-openeuler24.03-lts bash；docs/developer_guide.md: docker images；docs/developer_guide.md: docker exec -it <container-name> bash；origin/master:docs/zh/developer_guide.md: docker run -it -d --net=host --shm-size=1g \ --name <container-name> \ --device=/dev/davinci_manager:rwm \ --device=/dev/hisi_hdc:rwm \ --device=/dev/devmm_svm:rwm \ --device=/dev/davinci0:rwm \ -v /usr/local/Ascend/driver:/usr/local/Ascend/driver:ro \ -v /usr/local/Ascend/firmware/:/usr/local/Ascend/firmware:ro \ -v /usr/local/sbin:/usr/local/sbin:ro \ -v /path-to-weights:/path-to-weights:ro \ mindie:2.2.RC1-800I-A2-py311-openeuler24.03-lts bash；origin/master:docs/zh/developer_guide.md: docker images；origin/master:docs/zh/developer_guide.md: docker exec -it <container-name> bash
- 增量构建命令: `python3 setup.py bdist_wheel` -> 失败
- 增量构建实际探测耗时: `0.32s`
- 本地代码检测命令: `N/A` -> 未配置
- 本地代码检测实际探测耗时: `N/A`
- UT 命令: `python3 -m pip install -r requirements.txt && python3 -m pip install coverage && cd tests && bash run_test.sh` -> 失败
- UT 实际探测耗时: `0.27s`
- 增量构建失败摘要: `INFO:root:running bdist_wheel INFO:root:running build INFO:root:running build_py INFO:root:>>> Running build.sh to compile shared libraries... ERROR:root:Build script failed with return code 2 ERROR:root:Build script output: None Traceback (most recent call last):   File "/mnt/d/vbox/repos/MindIE-SD/setup.py", line 78, in run     subprocess.check_call(   File "/usr/lib/python3.12/subprocess.py", l`
- UT 失败摘要: `error: externally-managed-environment  × This environment is externally managed ╰─> To install Python packages system-wide, try apt install     python3-xyz, where xyz is the package you are trying to     install.          If you wish to install a non-Debian-packaged Python package,     create a virtual environment using python3 -m venv path/to/venv.     Then use path/to/venv/bin/python and path/to`
- PR 指标平台 / 时间窗: `gitcode` / 最近 `30` 天
- PR 采样数量 / Workflow 数量: `0` / `0`
- PR 执行时长: 平均 `N/A` / 中位 `N/A` / 最近一次 `N/A`
- PR 资源消耗: CPU: N/A; NPU: N/A
- AI 代码检视证据: N/A
- PR 采集说明: GitCode AI review detection requires a private token; set GITCODE_TOKEN to inspect PR comments
- 命令推断依据: container strategy: docker_documented；container environment note: docker is documented, but no runnable container definition was found；markdown scanned: 43 files；build/build.sh detected；tests/run_UT_test.sh detected
- Markdown 改进建议:
  - [medium/documentation/missing_code_check_docs] 仓库支持代码检测，但 Markdown 没有给出 lint / pre-commit 执行说明 | 证据: requirements.txt:pre-commit；tests\run_UT_test.sh:test-script；tests\run_test.sh:test-script | 建议: 补充代码检测章节，至少说明 lint 命令、自动修复命令和常见失败排查路径。
  - [high/documentation/container_docs_not_self_contained] Markdown 提到了容器路径，但仓库内没有可直接复现的容器定义 | 证据: docker/README.md；repository mentions Docker but does not provide a runnable Dockerfile, compose file, devcontainer, or workflow container image | 建议: 补充可直接执行的 `docker pull`、`docker load` 或 `docker build` 命令，或者在仓库内提供 Dockerfile / compose / devcontainer。
  - [high/repository/repository_script_issue] 构建 失败根因在仓库脚本内容或 CRLF/LF 行尾格式，不是 Markdown 描述不清 | 证据: 构建 command: python3 setup.py bdist_wheel；构建 status: failed；构建 failure: INFO:root:running bdist_wheel INFO:root:running build INFO:root:running build_py INFO:root:>>> Running build.sh to compile shared libraries... ERROR:root:Build script failed with return code 2 ERROR:root:Build script output: None Traceback  | 建议: 修复脚本为 LF 行尾，并用 `.gitattributes` 固化 shell 脚本换行格式；再加一条 CI 烟测保障。
  - [medium/mixed/execution_failure_needs_manual_triage] 测试 命令执行失败，需要继续区分是文档漂移还是仓库行为变化 | 证据: 测试 command: python3 -m pip install -r requirements.txt && python3 -m pip install coverage && cd tests && bash run_test.sh；测试 status: failed；测试 failure: error: externally-managed-environment  × This environment is externally managed ╰─> To install Python packages system-wide, try apt install     python3-xyz, where xyz is the package you are trying to     install.          If you wish to ins | 建议: 复核文档示例、依赖锁定和仓库脚本是否一致，并为该命令补一条 CI 烟测。
