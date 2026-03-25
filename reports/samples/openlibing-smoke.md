# 开源代码仓开发体验评估报告

| 仓库 | 编码风格是否有定义 | 代码检测是否支持 | 容器环境是否定义 | 容器环境本地可搭建 | 本地增量构建时间 | 本地代码检测时间 | 本地UT执行时间 | 代码检查规则数量 | 自动修复是否具备 | AI辅助代码检视是否支持 | PR执行时长平均值 | 单次PR资源CPU/NPU消耗量 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Ascend/memcache | 是 | 否 | 否 | 否 | N/A | N/A | N/A | N/A | 否 | 否 | N/A | CPU: N/A; NPU: N/A |
| Ascend/memfabric_hybrid | 是 | 否 | 否 | 否 | N/A | N/A | N/A | N/A | 否 | 否 | N/A | CPU: N/A; NPU: N/A |
| sgl-project/sgl-kernel-npu | 否 | 否 | 否 | 否 | N/A | N/A | N/A | N/A | 否 | 是 | 858.70s | CPU: 估算 15.33 core-min; NPU: N/A |

## Markdown 改进建议总览

| 分类 | 数量 |
| --- | --- |
| container_docs_not_self_contained | 1 |

## Ascend/memcache

- 本地路径: `D:\vbox\repos\repo_dev_eval_agent\.work\eval_xlsx_smoke\Ascend__memcache`
- Markdown 扫描文件数: `34`
- Markdown 相关文件: doc/build.md；doc/memcache_metaservice_HA.md；example/benchmark/README.md；example/cpp/README.md；example/python/README.md；origin/master:doc/build.md；origin/master:doc/memcache_metaservice_HA.md；origin/master:example/benchmark/README.md；... (+2)
- 编码风格是否定义: 是
- 编码风格证据: .clang-format
- 代码检测是否支持: 否
- 代码检测证据: N/A
- 自动修复是否具备: 否
- 自动修复证据: N/A
- 容器环境: 否 / 否 / `host`
- 容器定义文件: N/A
- 容器镜像线索: N/A
- 容器准备命令: `N/A`
- 容器环境说明: repository does not define Docker/devcontainer environment
- 规则统计明细: N/A
- 文档中的安装命令: example/cpp/README.md: source /usr/local/memfabric_hybrid/set_env.sh；example/cpp/README.md: source /usr/local/memcache_hybrid/set_env.sh；example/python/README.md: source /usr/local/memfabric_hybrid/set_env.sh；example/python/README.md: source /usr/local/memcache_hybrid/set_env.sh；origin/master:example/cpp/README.md: source /usr/local/memfabric_hybrid/set_env.sh；origin/master:example/cpp/README.md: source /usr/local/memcache_hybrid/set_env.sh；origin/master:example/python/README.md: source /usr/local/memfabric_hybrid/set_env.sh；origin/master:example/python/README.md: source /usr/local/memcache_hybrid/set_env.sh
- 文档中的构建命令: example/cpp/README.md: cmake . -B build；example/cpp/README.md: make -C build；origin/master:example/cpp/README.md: cmake . -B build；origin/master:example/cpp/README.md: make -C build
- 文档中的测试命令: N/A
- 文档中的代码检测命令: N/A
- 文档中的容器命令: doc/memcache_metaservice_HA.md: docker save my-image:latest -o my-image.tar；origin/master:doc/memcache_metaservice_HA.md: docker save my-image:latest -o my-image.tar
- 增量构建命令: `make -C build` -> 未执行
- 增量构建实际探测耗时: `N/A`
- 本地代码检测命令: `N/A` -> 未配置
- 本地代码检测实际探测耗时: `N/A`
- UT 命令: `N/A` -> 未配置
- UT 实际探测耗时: `N/A`
- PR 指标平台 / 时间窗: `gitcode` / 最近 `30` 天
- PR 采样数量 / Workflow 数量: `0` / `0`
- PR 执行时长: 平均 `N/A` / 中位 `N/A` / 最近一次 `N/A`
- PR 资源消耗: CPU: N/A; NPU: N/A
- AI 代码检视证据: N/A
- PR 采集说明: GitCode AI review detection requires a private token; set GITCODE_TOKEN to inspect PR comments
- 命令推断依据: markdown scanned: 34 files；documented build command: example/cpp/README.md
- Markdown 改进建议:
  - [high/documentation/container_docs_not_self_contained] Markdown 提到了容器路径，但仓库内没有可直接复现的容器定义 | 证据: N/A | 建议: 补充可直接执行的 `docker pull`、`docker load` 或 `docker build` 命令，或者在仓库内提供 Dockerfile / compose / devcontainer。

## Ascend/memfabric_hybrid

- 本地路径: `D:\vbox\repos\repo_dev_eval_agent\.work\eval_xlsx_smoke\Ascend__memfabric_hybrid`
- Markdown 扫描文件数: `58`
- Markdown 相关文件: doc/installation.md；doc/SECURITYNOTE.md；example/bm/BmBenchmark/README.md；example/bm/BmCpp/README.md；example/config_store/README.md；example/shm/AllReduce/README.md；example/shm/RDMADemo/README.md；example/shm/ShiftPutGet/README.md；... (+16)
- 编码风格是否定义: 是
- 编码风格证据: .clang-format
- 代码检测是否支持: 否
- 代码检测证据: N/A
- 自动修复是否具备: 否
- 自动修复证据: N/A
- 容器环境: 否 / 否 / `host`
- 容器定义文件: N/A
- 容器镜像线索: N/A
- 容器准备命令: `N/A`
- 容器环境说明: repository does not define Docker/devcontainer environment
- 规则统计明细: N/A
- 文档中的安装命令: example/bm/BmBenchmark/README.md: source /usr/local/memfabric_hybrid/set_env.sh；example/bm/BmCpp/README.md: source /usr/local/memfabric_hybrid/set_env.sh；origin/master:example/bm/BmBenchmark/README.md: source /usr/local/memfabric_hybrid/set_env.sh；origin/master:example/bm/BmCpp/README.md: source /usr/local/memfabric_hybrid/set_env.sh
- 文档中的构建命令: example/bm/BmBenchmark/README.md: cmake . -B build；example/bm/BmBenchmark/README.md: make -C build；example/bm/BmCpp/README.md: cmake . -B build；example/bm/BmCpp/README.md: make -C build；example/config_store/README.md: cmake . -B build；example/config_store/README.md: make -C build；example/trans/perf/README.md: cmake . -B build；example/trans/perf/README.md: make -C build；... (+8)
- 文档中的测试命令: N/A
- 文档中的代码检测命令: N/A
- 文档中的容器命令: N/A
- 增量构建命令: `make -C build` -> 未执行
- 增量构建实际探测耗时: `N/A`
- 本地代码检测命令: `N/A` -> 未配置
- 本地代码检测实际探测耗时: `N/A`
- UT 命令: `N/A` -> 未配置
- UT 实际探测耗时: `N/A`
- PR 指标平台 / 时间窗: `gitcode` / 最近 `30` 天
- PR 采样数量 / Workflow 数量: `0` / `0`
- PR 执行时长: 平均 `N/A` / 中位 `N/A` / 最近一次 `N/A`
- PR 资源消耗: CPU: N/A; NPU: N/A
- AI 代码检视证据: N/A
- PR 采集说明: GitCode AI review detection requires a private token; set GITCODE_TOKEN to inspect PR comments
- 命令推断依据: markdown scanned: 58 files；documented build command: example/bm/BmBenchmark/README.md
- Markdown 改进建议: N/A

## sgl-project/sgl-kernel-npu

- 本地路径: `D:\vbox\repos\repo_dev_eval_agent\.work\eval_xlsx_smoke\sgl-project__sgl-kernel-npu`
- Markdown 扫描文件数: `0`
- Markdown 相关文件: N/A
- 编码风格是否定义: 否
- 编码风格证据: N/A
- 代码检测是否支持: 否
- 代码检测证据: N/A
- 自动修复是否具备: 否
- 自动修复证据: N/A
- 容器环境: 否 / 否 / `host`
- 容器定义文件: N/A
- 容器镜像线索: N/A
- 容器准备命令: `N/A`
- 容器环境说明: repository does not define Docker/devcontainer environment
- 规则统计明细: N/A
- 文档中的安装命令: N/A
- 文档中的构建命令: N/A
- 文档中的测试命令: N/A
- 文档中的代码检测命令: N/A
- 文档中的容器命令: N/A
- 增量构建命令: `N/A` -> 未配置
- 增量构建实际探测耗时: `N/A`
- 本地代码检测命令: `N/A` -> 未配置
- 本地代码检测实际探测耗时: `N/A`
- UT 命令: `N/A` -> 未配置
- UT 实际探测耗时: `N/A`
- PR 指标平台 / 时间窗: `github` / 最近 `30` 天
- PR 采样数量 / Workflow 数量: `20` / `20`
- PR 执行时长: 平均 `858.70s` / 中位 `0.00s` / 最近一次 `0.00s`
- PR 资源消耗: CPU: 估算 15.33 core-min; NPU: N/A
- AI 代码检视证据: pr#406 review by gemini-code-assist[bot]；pr#406 comment by gemini-code-assist[bot]；pr#381 review by gemini-code-assist[bot]；pr#381 comment by gemini-code-assist[bot]；pr#399 review by gemini-code-assist[bot]；pr#399 comment by gemini-code-assist[bot]；pr#407 comment by gemini-code-assist[bot]；pr#401 review by gemini-code-assist[bot]；... (+28)
- PR 采集说明: collected from GitHub Actions and PR APIs within the last 30 days
- PR Run 证据: run:23477077508 PR Test for SGL-KERNEL-NPU (Ascend NPU) pull_request；run:23477077515 Lint pull_request；run:23475876449 Lint pull_request；run:23475876448 PR Test for SGL-KERNEL-NPU (Ascend NPU) pull_request；run:23468733092 Lint pull_request；run:23468733095 Build and Release SGL-Kernel-NPU pull_request；run:23468733104 PR Test for SGL-KERNEL-NPU (Ascend NPU) pull_request；run:23468521305 Build and Release SGL-Kernel-NPU pull_request；... (+12)
- Markdown 改进建议: N/A
- 错误: failed to clone/fetch repo: Cloning into 'D:\vbox\repos\repo_dev_eval_agent\.work\eval_xlsx_smoke\sgl-project__sgl-kernel-npu'...
fatal: unable to access 'https://github.com/sgl-project/sgl-kernel-npu.git/': Failed to connect to github.com port 443 after 21084 ms: Could not connect to server
