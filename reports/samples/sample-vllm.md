# 开源代码仓开发体验评估报告

| 仓库 | 编码风格是否有定义 | 代码检测是否支持 | 容器环境是否定义 | 容器环境本地可搭建 | 本地增量构建时间 | 本地代码检测时间 | 本地UT执行时间 | 代码检查规则数量 | 自动修复是否具备 | AI辅助代码检视是否支持 | PR执行时长平均值 | 单次PR资源CPU/NPU消耗量 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| vllm-project/vllm | 是 | 是 | 是 | 是 | N/A | N/A | N/A | 41 | 是 | 是 | 58.10s | CPU: 估算 73.80 core-min; NPU: N/A |

## Markdown 改进建议总览

当前没有识别出 Markdown 与实际执行之间的明显偏差。

## vllm-project/vllm

- 本地路径: `D:\vbox\repos\vllm_upstream`
- Markdown 扫描文件数: `482`
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
- 增量构建命令: `VLLM_USE_PRECOMPILED=1 uv pip install -e .` -> 未执行
- 增量构建实际探测耗时: `N/A`
- 本地代码检测命令: `pre-commit run -a` -> 未执行
- 本地代码检测实际探测耗时: `N/A`
- UT 命令: `pytest tests/v1/structured_output/test_backend_xgrammar.py -q` -> 未执行
- UT 实际探测耗时: `N/A`
- PR 指标平台 / 时间窗: `github` / 最近 `30` 天
- PR 采样数量 / Workflow 数量: `10` / `20`
- PR 执行时长: 平均 `58.10s` / 中位 `17.50s` / 最近一次 `20.00s`
- PR 资源消耗: CPU: 估算 73.80 core-min; NPU: N/A
- AI 代码检视证据: pr#37975 review by gemini-code-assist[bot]；pr#37975 comment by gemini-code-assist[bot]；pr#37935 review by gemini-code-assist[bot]；pr#38061 review by gemini-code-assist[bot]；pr#38059 review by gemini-code-assist[bot]；pr#36142 review by chatgpt-codex-connector[bot]；pr#36142 review by gemini-code-assist[bot]；pr#37835 review by gemini-code-assist[bot]；... (+4)
- PR 采集说明: collected from GitHub Actions and PR APIs within the last 30 days
- PR Run 证据: run:22335906128 BC Lint pull_request；run:22335906118 pre-commit pull_request；run:22335896176 BC Lint pull_request；run:22335896188 pre-commit pull_request；run:22335890061 pre-commit pull_request；run:22335890086 BC Lint pull_request；run:22335866651 BC Lint pull_request；run:22335866630 pre-commit pull_request；... (+12)
- 命令推断依据: container strategy: docker_build；container environment can be prepared locally；markdown scanned: 482 files；tests/ or pytest.ini detected；.pre-commit-config.yaml detected；documented build command: docs/contributing/README.md
- Markdown 改进建议: N/A
