from __future__ import annotations

import json
import re
import subprocess
import xml.etree.ElementTree as ET
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from .repo_eval_models import (
    ContainerEnvironmentAssessment,
    ContainerRuntimeProbe,
    DocumentationAssessment,
    DocumentationCommand,
    RuleCountDetail,
    StaticAnalysisResult,
)

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore[no-redef]


STYLE_FILES = (
    ".editorconfig",
    ".clang-format",
    ".prettierrc",
    ".prettierrc.json",
    ".prettierrc.yml",
    ".prettierrc.yaml",
    "ruff.toml",
    ".ruff.toml",
    "rustfmt.toml",
    ".rustfmt.toml",
)

CHECK_FILES = (
    "pytest.ini",
    "tox.ini",
    ".pre-commit-config.yaml",
    ".coveragerc",
)

CHECK_KEYWORDS = (
    "ruff",
    "eslint",
    "golangci-lint",
    "shellcheck",
    "mypy",
    "pytest",
    "pre-commit",
    "checkstyle",
    "spotbugs",
    "pmd",
    "markdownlint",
    "yamllint",
    "actionlint",
    "trivy",
    "semgrep",
    "codeql",
)

AUTO_FIX_KEYWORDS = (
    "autofix.ci",
    "--fix",
    "ruff format",
    "prettier",
    "clang-format",
    "shfmt -w",
    "black ",
    "isort ",
)

AI_REVIEW_KEYWORDS = (
    "copilot",
    "coderabbit",
    "qodo",
    "openai",
    "codex",
    "gemini",
)

FROM_RE = re.compile(r"^\s*FROM\s+([^\s]+)(?:\s+AS\s+([^\s]+))?", re.IGNORECASE)
ARG_RE = re.compile(r"^\s*ARG\s+([A-Za-z0-9_]+)(?:=(.+))?")
DOCKERFILE_NAME_RE = re.compile(r"^Dockerfile(?:\..+)?$")
FENCED_CODE_RE = re.compile(
    r"```(?P<lang>[^\n`]*)\n(?P<body>.*?)```",
    re.DOTALL,
)

GPU_IMAGE_HINTS = (
    "cuda",
    "nvidia",
    "rocm",
    "xpu",
    "tpu",
    "ascend",
)

IGNORED_REPO_DIRS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".trae",
    ".venv",
    ".work",
    "build",
    "dist",
    "node_modules",
    "reports",
    "__pycache__",
}

DOC_COMMAND_HINTS = (
    "pip install",
    "uv pip install",
    "uv venv",
    "python setup.py",
    "pytest",
    "pre-commit",
    "ruff",
    "mypy",
    "docker ",
    "podman ",
    "cmake ",
    "make ",
    "bash ",
    "git clone ",
)

DOC_BUILD_HINTS = (
    "uv pip install -e .",
    "uv pip install --editable .",
    "pip install -e .",
    "python setup.py bdist_wheel",
    "cmake --build",
    "cmake --preset",
    "make ",
)

DOC_INSTALL_HINTS = (
    "pip install ",
    "uv pip install ",
    "uv venv",
    "python -m venv",
    ".run --install",
    "chmod +x ",
    "source ",
)

DOC_TEST_HINTS = (
    "pytest",
    "ctest",
    "unittest",
    "bash run_test.sh",
    "bash run_UT_test.sh",
    "run_test.sh",
    "run_UT_test.sh",
    "python tests/",
)

DOC_CHECK_HINTS = (
    "pre-commit",
    "ruff",
    "mypy",
    "eslint",
    "markdownlint",
    "actionlint",
    "shellcheck",
    "golangci-lint",
)

DOC_CONTAINER_HINTS = (
    "docker ",
    "docker compose",
    "docker pull",
    "docker run",
    "docker build",
    "podman ",
)


def _safe_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="utf-8", errors="replace")


def _safe_load_yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(_safe_read_text(path))
    except Exception:
        return None


def _safe_load_json(path: Path) -> Any:
    try:
        return json.loads(_safe_read_text(path))
    except Exception:
        return None


def _safe_load_toml(path: Path) -> Any:
    try:
        return tomllib.loads(_safe_read_text(path))
    except Exception:
        return None


def _collect_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        out: list[str] = []
        for item in value.values():
            out.extend(_collect_strings(item))
        return out
    if isinstance(value, list):
        out: list[str] = []
        for item in value:
            out.extend(_collect_strings(item))
        return out
    return []


def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def _relative_to_root(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _repo_rglob(root: Path, pattern: str) -> list[Path]:
    out: list[Path] = []
    for path in root.rglob(pattern):
        if any(part in IGNORED_REPO_DIRS for part in path.parts):
            continue
        if not path.is_file():
            continue
        out.append(path)
    return out


def _has_gpu_hint(value: str) -> bool:
    lowered = value.lower()
    return any(hint in lowered for hint in GPU_IMAGE_HINTS)


def _normalize_shell_command(path: str) -> str:
    return path.replace("\\", "/")


def _short_text(text: str, limit: int = 160) -> str:
    return (text or "").strip().replace("\r", " ").replace("\n", " ")[:limit]


def _text_has_any(text: str, needles: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(needle in lowered for needle in needles)


def _markdown_files(root: Path) -> list[Path]:
    files = _repo_rglob(root, "*.md")
    files.extend(_repo_rglob(root, "*.mdx"))
    return sorted(set(files))


def _split_markdown_command_block(body: str) -> list[str]:
    commands: list[str] = []
    current: list[str] = []
    for raw_line in body.splitlines():
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped:
            if current:
                commands.append("\n".join(current))
                current = []
            continue
        if stripped.startswith("$ "):
            stripped = stripped[2:]
        elif stripped.startswith(">"):
            stripped = stripped[1:].lstrip()
            if stripped.startswith("$ "):
                stripped = stripped[2:]
        if stripped.startswith("#") and not current:
            continue
        current.append(stripped)
        if stripped.endswith("\\") or stripped.endswith("`"):
            continue
        commands.append("\n".join(current))
        current = []
    if current:
        commands.append("\n".join(current))
    return [cmd for cmd in commands if cmd.strip()]


def _classify_documentation_command(command: str) -> list[str]:
    categories: list[str] = []
    lowered = command.lower()
    if _text_has_any(lowered, DOC_CONTAINER_HINTS):
        categories.append("container")
    if _text_has_any(lowered, DOC_CHECK_HINTS):
        categories.append("check")
    if _text_has_any(lowered, DOC_TEST_HINTS):
        categories.append("test")
    if _text_has_any(lowered, DOC_BUILD_HINTS):
        categories.append("build")
    if _text_has_any(lowered, DOC_INSTALL_HINTS):
        categories.append("install")
    return categories


def _scan_markdown_text(
    *,
    source_name: str,
    text: str,
    assessment: DocumentationAssessment,
    commands_seen: set[tuple[str, str, str]],
) -> None:
    relevant = False

    if _text_has_any(text, DOC_COMMAND_HINTS + DOC_CONTAINER_HINTS):
        relevant = True

    for match in FENCED_CODE_RE.finditer(text):
        lang = (match.group("lang") or "").strip().lower()
        body = match.group("body") or ""
        if lang and not any(
            hint in lang
            for hint in ("bash", "shell", "console", "sh", "zsh", "pwsh", "powershell")
        ):
            if not _text_has_any(body, DOC_COMMAND_HINTS + DOC_CONTAINER_HINTS):
                continue
        elif not _text_has_any(body, DOC_COMMAND_HINTS + DOC_CONTAINER_HINTS):
            continue

        relevant = True
        for command in _split_markdown_command_block(body):
            categories = _classify_documentation_command(command)
            for category in categories:
                key = (source_name, category, command)
                if key in commands_seen:
                    continue
                commands_seen.add(key)
                assessment.commands.append(
                    DocumentationCommand(
                        source_file=source_name,
                        category=category,
                        command=command,
                    )
                )

    if relevant:
        _append_unique(assessment.relevant_files, source_name)


def _git_command(
    root: Path,
    args: list[str],
) -> tuple[int, str, str]:
    proc = subprocess.run(
        ["git", *args],
        cwd=str(root),
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
        timeout=60,
    )
    return proc.returncode, proc.stdout or "", proc.stderr or ""


def _scan_markdown_docs(root: Path) -> DocumentationAssessment:
    assessment = DocumentationAssessment()
    commands_seen: set[tuple[str, str, str]] = set()

    for path in _markdown_files(root):
        assessment.markdown_files_scanned += 1
        rel = _relative_to_root(root, path)
        _scan_markdown_text(
            source_name=rel,
            text=_safe_read_text(path),
            assessment=assessment,
            commands_seen=commands_seen,
        )

    if assessment.markdown_files_scanned and not assessment.relevant_files:
        assessment.notes.append(
            "markdown scanned, but no install/build/test/check instructions were extracted"
        )
    return assessment


def _scan_markdown_docs_from_git_ref(root: Path, ref: str) -> DocumentationAssessment:
    assessment = DocumentationAssessment()
    commands_seen: set[tuple[str, str, str]] = set()
    rc, stdout, stderr = _git_command(root, ["ls-tree", "-r", "--name-only", ref])
    if rc != 0:
        assessment.notes.append(
            f"failed to scan markdown from ref {ref}: {_short_text(stderr)}"
        )
        return assessment

    for raw in stdout.splitlines():
        rel = raw.strip()
        lowered = rel.lower()
        if not lowered.endswith(".md") and not lowered.endswith(".mdx"):
            continue
        rc_show, file_text, show_stderr = _git_command(root, ["show", f"{ref}:{rel}"])
        assessment.markdown_files_scanned += 1
        if rc_show != 0:
            assessment.notes.append(
                f"failed to read markdown from ref {ref}:{rel}: {_short_text(show_stderr)}"
            )
            continue
        _scan_markdown_text(
            source_name=f"{ref}:{rel}",
            text=file_text,
            assessment=assessment,
            commands_seen=commands_seen,
        )

    if assessment.markdown_files_scanned and not assessment.relevant_files:
        assessment.notes.append(
            f"markdown ref scanned ({ref}), but no install/build/test/check instructions were extracted"
        )
    return assessment


def _merge_documentation_assessments(
    *items: DocumentationAssessment,
) -> DocumentationAssessment:
    merged = DocumentationAssessment()
    seen_commands: set[tuple[str, str, str]] = set()
    for item in items:
        merged.markdown_files_scanned += item.markdown_files_scanned
        for path in item.relevant_files:
            _append_unique(merged.relevant_files, path)
        for command in item.commands:
            key = (command.source_file, command.category, command.command)
            if key in seen_commands:
                continue
            seen_commands.add(key)
            merged.commands.append(command)
        for note in item.notes:
            _append_unique(merged.notes, note)
    return merged


def _documented_commands(
    documentation: DocumentationAssessment,
    category: str,
) -> list[DocumentationCommand]:
    return [item for item in documentation.commands if item.category == category]


def _select_documented_command(
    documentation: DocumentationAssessment,
    category: str,
) -> DocumentationCommand | None:
    candidates = _documented_commands(documentation, category)
    if not candidates:
        return None

    def source_priority(item: DocumentationCommand) -> int:
        source = item.source_file.lower()
        if source.startswith("docs/contributing/"):
            return 0
        if source.startswith("docs/getting_started/"):
            return 1
        if source in {"readme.md", "contributing.md"}:
            return 2
        if source.startswith("docs/deployment/"):
            return 3
        if source.startswith("docs/"):
            return 4
        if source.startswith("examples/"):
            return 6
        if source.startswith("benchmarks/") or source.startswith(".buildkite/"):
            return 7
        return 5

    def score(item: DocumentationCommand) -> tuple[int, int, int]:
        lowered = item.command.lower()
        preferred_patterns = {
            "build": (
                "uv pip install -e .",
                "uv pip install --editable .",
                "pip install -e .",
                "python setup.py bdist_wheel",
                "cmake --build",
            ),
            "install": (
                "uv venv",
                "python -m venv",
                "uv pip install ",
                "pip install ",
            ),
            "test": (
                "pytest ",
                "bash run_test.sh",
                "bash run_ut_test.sh",
            ),
            "check": (
                "pre-commit run -a",
                "pre-commit run",
                "ruff check .",
                "mypy ",
            ),
            "container": (
                "docker pull",
                "docker build",
                "docker run",
                "podman run",
            ),
        }
        patterns = preferred_patterns.get(category, ())
        for index, pattern in enumerate(patterns):
            if pattern in lowered:
                return (source_priority(item), 0, index)
        return (source_priority(item), 1, len(lowered))

    return sorted(candidates, key=score)[0]


def _doc_command_label(item: DocumentationCommand) -> str:
    return f"{item.source_file}: {item.command.replace(chr(10), ' ')}"


def _parse_dockerfile_images(path: Path) -> tuple[list[str], bool]:
    text = _safe_read_text(path)
    images: list[str] = []
    arg_defaults: dict[str, str] = {}
    stage_names: set[str] = set()
    gpu_required = False

    for line in text.splitlines():
        arg_match = ARG_RE.match(line)
        if arg_match:
            name = arg_match.group(1)
            value = (arg_match.group(2) or "").strip().strip('"').strip("'")
            if value and ("/" in value or ":" in value):
                arg_defaults[name] = value
                if _has_gpu_hint(value):
                    gpu_required = True

        from_match = FROM_RE.match(line)
        if not from_match:
            continue
        image = from_match.group(1).strip()
        alias = (from_match.group(2) or "").strip()
        if image.startswith("${") and image.endswith("}"):
            arg_name = image[2:-1].split(":-", 1)[0]
            image = arg_defaults.get(arg_name, image)
        elif image.startswith("$"):
            arg_name = image[1:]
            image = arg_defaults.get(arg_name, image)

        if image not in stage_names:
            _append_unique(images, image)
            if _has_gpu_hint(image):
                gpu_required = True
        if alias:
            stage_names.add(alias)
        if _has_gpu_hint(image):
            gpu_required = True

    return images, gpu_required


def _extract_image_refs(value: Any) -> list[str]:
    out: list[str] = []
    if isinstance(value, str):
        _append_unique(out, value)
        return out
    if isinstance(value, dict):
        image = value.get("image")
        if isinstance(image, str):
            _append_unique(out, image)
    return out


def _parse_workflow_container_images(root: Path) -> list[str]:
    workflow_dir = root / ".github" / "workflows"
    if not workflow_dir.exists():
        return []
    images: list[str] = []
    files = list(workflow_dir.glob("*.yml")) + list(workflow_dir.glob("*.yaml"))
    for path in files:
        data = _safe_load_yaml(path)
        if not isinstance(data, dict):
            continue
        jobs = data.get("jobs", {})
        if not isinstance(jobs, dict):
            continue
        for job in jobs.values():
            if not isinstance(job, dict):
                continue
            for image in _extract_image_refs(job.get("container")):
                _append_unique(images, image)
            services = job.get("services", {})
            if not isinstance(services, dict):
                continue
            for service in services.values():
                for image in _extract_image_refs(service):
                    _append_unique(images, image)
    return images


def _parse_compose_images(path: Path) -> tuple[list[str], bool]:
    data = _safe_load_yaml(path)
    if not isinstance(data, dict):
        return [], False
    services = data.get("services", {})
    if not isinstance(services, dict):
        return [], False
    images: list[str] = []
    gpu_required = False
    for service in services.values():
        if not isinstance(service, dict):
            continue
        image = service.get("image")
        if isinstance(image, str):
            _append_unique(images, image)
            if _has_gpu_hint(image):
                gpu_required = True
    return images, gpu_required


def _resolve_devcontainer_paths(
    root: Path, path: Path
) -> tuple[list[str], list[str], list[str]]:
    data = _safe_load_json(path)
    if not isinstance(data, dict):
        return [], [], []

    dockerfiles: list[str] = []
    compose_files: list[str] = []
    images: list[str] = []
    parent = path.parent

    build = data.get("build")
    if isinstance(build, dict):
        dockerfile = build.get("dockerfile") or build.get("dockerFile")
        if isinstance(dockerfile, str):
            resolved = (parent / dockerfile).resolve()
            if resolved.exists():
                _append_unique(dockerfiles, _relative_to_root(root, resolved))
    dockerfile = data.get("dockerFile")
    if isinstance(dockerfile, str):
        resolved = (parent / dockerfile).resolve()
        if resolved.exists():
            _append_unique(dockerfiles, _relative_to_root(root, resolved))

    compose = data.get("dockerComposeFile")
    if isinstance(compose, str):
        resolved = (parent / compose).resolve()
        if resolved.exists():
            _append_unique(compose_files, _relative_to_root(root, resolved))
    elif isinstance(compose, list):
        for item in compose:
            if not isinstance(item, str):
                continue
            resolved = (parent / item).resolve()
            if resolved.exists():
                _append_unique(compose_files, _relative_to_root(root, resolved))

    image = data.get("image")
    if isinstance(image, str):
        _append_unique(images, image)

    return dockerfiles, compose_files, images


def _slugify_repo_name(path: Path) -> str:
    return re.sub(r"[^a-z0-9_.-]+", "-", path.name.lower()).strip("-") or "repo-eval"


def _which_available(program: str) -> bool:
    try:
        proc = subprocess.run(
            [program, "--version"],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            check=False,
            timeout=10,
        )
    except Exception:
        return False
    return proc.returncode == 0


@lru_cache(maxsize=1)
def _probe_container_runtime() -> ContainerRuntimeProbe:
    if _which_available("docker"):
        probe = ContainerRuntimeProbe(engine="docker", cli_available=True)
        probe.evidence.append("docker cli available")
        try:
            server = subprocess.run(
                ["docker", "info", "--format", "{{.ServerVersion}}"],
                text=True,
                encoding="utf-8",
                errors="replace",
                capture_output=True,
                check=False,
                timeout=15,
            )
            if server.returncode == 0:
                probe.daemon_available = True
                probe.server_version = (server.stdout or "").strip()
                if probe.server_version:
                    probe.evidence.append(f"docker daemon {probe.server_version}")
            else:
                detail = _short_text(server.stderr or server.stdout, 160)
                if detail:
                    probe.evidence.append(f"docker daemon unavailable: {detail}")
        except Exception as exc:
            probe.evidence.append(f"docker daemon probe failed: {exc}")

        if probe.daemon_available:
            try:
                runtimes = subprocess.run(
                    ["docker", "info", "--format", "{{json .Runtimes}}"],
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    capture_output=True,
                    check=False,
                    timeout=15,
                )
                if runtimes.returncode == 0:
                    data = json.loads((runtimes.stdout or "{}").strip() or "{}")
                    if isinstance(data, dict) and "nvidia" in data:
                        probe.nvidia_runtime_available = True
                        probe.evidence.append("docker nvidia runtime available")
            except Exception:
                pass
        return probe

    if _which_available("podman"):
        probe = ContainerRuntimeProbe(engine="podman", cli_available=True)
        probe.evidence.append("podman cli available")
        return probe

    return ContainerRuntimeProbe(engine="", cli_available=False, daemon_available=False)


def _scan_container_environment(root: Path) -> ContainerEnvironmentAssessment:
    assessment = ContainerEnvironmentAssessment()
    assessment.runtime = _probe_container_runtime()

    dockerfiles = [
        path for path in _repo_rglob(root, "*") if DOCKERFILE_NAME_RE.match(path.name)
    ]
    compose_files = []
    for pattern in (
        "docker-compose.yml",
        "docker-compose.yaml",
        "compose.yml",
        "compose.yaml",
    ):
        compose_files.extend(_repo_rglob(root, pattern))
    devcontainer_files = _repo_rglob(root, "devcontainer.json")

    reference_files: list[Path] = []
    docker_readme = root / "docker" / "README.md"
    if docker_readme.exists():
        reference_files.append(docker_readme)

    workflow_images = _parse_workflow_container_images(root)
    base_images: list[str] = []
    requires_gpu = False

    for path in dockerfiles:
        images, gpu_required = _parse_dockerfile_images(path)
        requires_gpu = requires_gpu or gpu_required
        for image in images:
            _append_unique(base_images, image)

    compose_images: list[str] = []
    for path in compose_files:
        images, gpu_required = _parse_compose_images(path)
        requires_gpu = requires_gpu or gpu_required
        for image in images:
            _append_unique(compose_images, image)

    resolved_devcontainer_dockerfiles: list[str] = []
    resolved_devcontainer_compose: list[str] = []
    devcontainer_images: list[str] = []
    for path in devcontainer_files:
        docker_refs, compose_refs, images = _resolve_devcontainer_paths(root, path)
        for item in docker_refs:
            _append_unique(resolved_devcontainer_dockerfiles, item)
        for item in compose_refs:
            _append_unique(resolved_devcontainer_compose, item)
        for item in images:
            _append_unique(devcontainer_images, item)
            if _has_gpu_hint(item):
                requires_gpu = True

    dockerfile_rel = sorted({_relative_to_root(root, path) for path in dockerfiles})
    compose_rel = sorted({_relative_to_root(root, path) for path in compose_files})
    devcontainer_rel = sorted(
        {_relative_to_root(root, path) for path in devcontainer_files}
    )
    reference_rel = sorted({_relative_to_root(root, path) for path in reference_files})

    for item in resolved_devcontainer_dockerfiles:
        _append_unique(dockerfile_rel, item)
    for item in resolved_devcontainer_compose:
        _append_unique(compose_rel, item)

    for image in compose_images + devcontainer_images:
        _append_unique(base_images, image)
        if _has_gpu_hint(image):
            requires_gpu = True
    for image in workflow_images:
        if _has_gpu_hint(image):
            requires_gpu = True

    assessment.dockerfiles = sorted(dockerfile_rel)
    assessment.compose_files = sorted(compose_rel)
    assessment.devcontainer_files = sorted(devcontainer_rel)
    assessment.reference_files = sorted(reference_rel)
    assessment.base_images = sorted(base_images)
    assessment.workflow_images = sorted(workflow_images)
    assessment.requires_gpu = requires_gpu

    assessment.defined = bool(
        assessment.dockerfiles
        or assessment.compose_files
        or assessment.devcontainer_files
        or assessment.reference_files
        or assessment.workflow_images
    )
    assessment.runnable_definition_present = bool(
        assessment.dockerfiles
        or assessment.compose_files
        or assessment.devcontainer_files
        or assessment.workflow_images
    )

    if assessment.dockerfiles:
        assessment.preferred_strategy = "docker_build"
        first = _normalize_shell_command(assessment.dockerfiles[0])
        assessment.inferred_setup_command = (
            f"docker build -f {first} -t repo-eval/{_slugify_repo_name(root)}:latest ."
        )
        assessment.setup_evidence.append(f"dockerfile:{assessment.dockerfiles[0]}")
    elif assessment.compose_files:
        assessment.preferred_strategy = "docker_compose"
        first = _normalize_shell_command(assessment.compose_files[0])
        assessment.inferred_setup_command = f"docker compose -f {first} up --build"
        assessment.setup_evidence.append(f"compose:{assessment.compose_files[0]}")
    elif assessment.devcontainer_files:
        assessment.preferred_strategy = "devcontainer"
        assessment.setup_evidence.append(
            f"devcontainer:{assessment.devcontainer_files[0]}"
        )
        if assessment.base_images:
            assessment.inferred_setup_command = (
                f"docker pull {assessment.base_images[0]}"
            )
    elif assessment.workflow_images:
        assessment.preferred_strategy = "docker_image"
        assessment.setup_evidence.append(
            f"workflow-container:{assessment.workflow_images[0]}"
        )
        assessment.inferred_setup_command = (
            f"docker pull {assessment.workflow_images[0]}"
        )
    elif assessment.reference_files:
        assessment.preferred_strategy = "docker_documented"
        assessment.setup_evidence.append(f"docker-doc:{assessment.reference_files[0]}")

    assessment.setup_evidence.extend(assessment.runtime.evidence[:3])

    if not assessment.defined:
        assessment.note = "repository does not define Docker/devcontainer environment"
        return assessment

    if not assessment.runnable_definition_present:
        assessment.setup_blockers.append(
            "repository mentions Docker but does not provide a runnable Dockerfile, compose file, devcontainer, or workflow container image"
        )
        assessment.note = (
            "docker is documented, but no runnable container definition was found"
        )
        return assessment

    if not assessment.runtime.cli_available:
        assessment.setup_blockers.append("no local docker/podman CLI available")
        assessment.note = (
            "container definition exists, but no local container CLI was found"
        )
        return assessment

    if (
        assessment.runtime.engine == "docker"
        and not assessment.runtime.daemon_available
    ):
        assessment.setup_blockers.append(
            "docker CLI exists but daemon is not reachable"
        )
        assessment.note = (
            "container definition exists, but Docker daemon is not reachable"
        )
        return assessment

    if assessment.requires_gpu and assessment.runtime.engine == "docker":
        if not assessment.runtime.nvidia_runtime_available:
            assessment.setup_blockers.append(
                "repository container images look GPU-oriented, but docker nvidia runtime was not detected"
            )
            assessment.note = (
                "container definition exists, but GPU runtime support is missing"
            )
            return assessment
        assessment.setup_evidence.append("gpu-capable docker runtime detected")

    assessment.setup_supported_locally = True
    assessment.note = "container environment can be prepared locally"
    return assessment


def _parse_ruff_rule_count(root: Path) -> RuleCountDetail | None:
    candidates = [root / "ruff.toml", root / ".ruff.toml", root / "pyproject.toml"]
    for candidate in candidates:
        if not candidate.exists():
            continue
        data = _safe_load_toml(candidate)
        if not isinstance(data, dict):
            continue
        if candidate.name == "pyproject.toml":
            tool = data.get("tool", {})
            ruff = tool.get("ruff", {}) if isinstance(tool, dict) else {}
            lint = ruff.get("lint", {}) if isinstance(ruff, dict) else {}
        else:
            lint = data.get("lint", {}) if isinstance(data, dict) else {}
        if not isinstance(lint, dict):
            continue
        selectors: list[str] = []
        for key in ("select", "extend-select", "ignore", "extend-ignore"):
            value = lint.get(key)
            if isinstance(value, list):
                selectors.extend(str(item) for item in value)
        if selectors:
            return RuleCountDetail(
                source=str(candidate.relative_to(root)),
                count=len(selectors),
                note="explicit Ruff selectors",
            )
        return RuleCountDetail(
            source=str(candidate.relative_to(root)),
            count=None,
            note="Ruff config present but no explicit selector count found",
        )
    return None


def _parse_golangci_rule_count(root: Path) -> RuleCountDetail | None:
    for name in (".golangci.yml", ".golangci.yaml", ".golangci.toml"):
        path = root / name
        if not path.exists():
            continue
        data = (
            _safe_load_toml(path) if path.suffix == ".toml" else _safe_load_yaml(path)
        )
        if not isinstance(data, dict):
            continue
        linters = data.get("linters", {})
        if isinstance(linters, dict):
            enabled = linters.get("enable")
            if isinstance(enabled, list):
                return RuleCountDetail(
                    source=name,
                    count=len(enabled),
                    note="enabled golangci-lint linters",
                )
        return RuleCountDetail(
            source=name,
            count=None,
            note="golangci-lint config present but explicit enabled linters not found",
        )
    return None


def _parse_pre_commit_hooks(root: Path) -> RuleCountDetail | None:
    path = root / ".pre-commit-config.yaml"
    if not path.exists():
        return None
    data = _safe_load_yaml(path)
    if not isinstance(data, dict):
        return RuleCountDetail(
            source=".pre-commit-config.yaml",
            count=None,
            note="pre-commit config present but unparsable",
        )
    repos = data.get("repos", [])
    count = 0
    if isinstance(repos, list):
        for repo in repos:
            hooks = repo.get("hooks", []) if isinstance(repo, dict) else []
            if isinstance(hooks, list):
                count += len(hooks)
    return RuleCountDetail(
        source=".pre-commit-config.yaml",
        count=count,
        note="pre-commit hook count",
    )


def _parse_package_json_rule_count(root: Path) -> RuleCountDetail | None:
    path = root / "package.json"
    if not path.exists():
        return None
    data = _safe_load_json(path)
    if not isinstance(data, dict):
        return None
    scripts = data.get("scripts", {})
    if not isinstance(scripts, dict):
        return None
    explicit = [
        name
        for name in scripts
        if any(key in name.lower() for key in ("lint", "format", "check"))
    ]
    if explicit:
        return RuleCountDetail(
            source="package.json",
            count=len(explicit),
            note="lint/format/check scripts",
        )
    return None


def _parse_eslint_rule_count(root: Path) -> RuleCountDetail | None:
    for name in (".eslintrc", ".eslintrc.json", ".eslintrc.yaml", ".eslintrc.yml"):
        path = root / name
        if not path.exists():
            continue
        data = (
            _safe_load_json(path)
            if "json" in name or name == ".eslintrc"
            else _safe_load_yaml(path)
        )
        if isinstance(data, dict) and isinstance(data.get("rules"), dict):
            return RuleCountDetail(
                source=name,
                count=len(data["rules"]),
                note="explicit ESLint rules",
            )
        return RuleCountDetail(
            source=name,
            count=None,
            note="ESLint config present but explicit rules not parsed",
        )
    for name in ("eslint.config.js", "eslint.config.mjs", "eslint.config.cjs"):
        if (root / name).exists():
            return RuleCountDetail(
                source=name,
                count=None,
                note="ESLint config present in JS format",
            )
    return None


def _parse_checkstyle_rule_count(root: Path) -> RuleCountDetail | None:
    for name in (
        "checkstyle.xml",
        ".checkstyle.xml",
        "config/checkstyle/checkstyle.xml",
    ):
        path = root / name
        if not path.exists():
            continue
        try:
            tree = ET.parse(path)
        except Exception:
            return RuleCountDetail(
                source=name, count=None, note="checkstyle xml unparsable"
            )
        modules = [
            elem.attrib.get("name", "") for elem in tree.iter() if elem.tag == "module"
        ]
        count = len([item for item in modules if item not in {"Checker", "TreeWalker"}])
        return RuleCountDetail(
            source=name,
            count=count,
            note="Checkstyle modules excluding root wrappers",
        )
    return None


def _parse_pyproject_signals(root: Path, result: StaticAnalysisResult) -> None:
    path = root / "pyproject.toml"
    if not path.exists():
        return
    data = _safe_load_toml(path)
    if not isinstance(data, dict):
        return
    tool = data.get("tool", {})
    if not isinstance(tool, dict):
        return
    for key in ("black", "ruff", "isort", "mypy", "pylint", "pytest", "coverage"):
        if key in tool:
            _append_unique(result.style_evidence, f"pyproject.toml:tool.{key}")
    if "ruff" in tool:
        _append_unique(result.check_tools, "ruff")
    if "mypy" in tool:
        _append_unique(result.check_tools, "mypy")
    if "pylint" in tool:
        _append_unique(result.check_tools, "pylint")
    if any(key in tool for key in ("black", "ruff", "isort")):
        _append_unique(result.auto_fix_evidence, "pyproject.toml formatter config")


def _detect_from_root_files(root: Path, result: StaticAnalysisResult) -> None:
    for name in STYLE_FILES:
        if (root / name).exists():
            _append_unique(result.style_evidence, name)
    for name in CHECK_FILES:
        if (root / name).exists():
            _append_unique(result.check_tools, name)
    for name in (
        "package.json",
        "go.mod",
        "Cargo.toml",
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
    ):
        if (root / name).exists():
            _append_unique(result.style_evidence, name)


def _detect_from_requirements(root: Path, result: StaticAnalysisResult) -> None:
    for name in ("requirements.txt", "requirements-dev.txt", "requirements/test.txt"):
        path = root / name
        if not path.exists():
            continue
        lowered = _safe_read_text(path).lower()
        if "pre-commit" in lowered:
            _append_unique(result.check_tools, f"{name}:pre-commit")
        if "pytest" in lowered:
            _append_unique(result.check_tools, f"{name}:pytest")
        if "coverage" in lowered:
            _append_unique(result.check_tools, f"{name}:coverage")


def _detect_from_shell_scripts(root: Path, result: StaticAnalysisResult) -> None:
    candidates = [
        root / "build" / "build.sh",
        root / "tests" / "run_UT_test.sh",
        root / "tests" / "run_test.sh",
    ]
    for path in candidates:
        if not path.exists():
            continue
        text = _safe_read_text(path).lower()
        rel = str(path.relative_to(root))
        if "pytest" in text or "coverage" in text or "unittest" in text:
            _append_unique(result.check_tools, f"{rel}:test-script")
        if "--fix" in text or "prettier" in text or "ruff format" in text:
            _append_unique(result.auto_fix_evidence, f"{rel}:autofix")


def _detect_from_package_json(root: Path, result: StaticAnalysisResult) -> None:
    path = root / "package.json"
    if not path.exists():
        return
    data = _safe_load_json(path)
    if not isinstance(data, dict):
        return
    scripts = data.get("scripts", {})
    if not isinstance(scripts, dict):
        return
    for name, command in scripts.items():
        lowered = f"{name} {command}".lower()
        if any(keyword in lowered for keyword in CHECK_KEYWORDS):
            _append_unique(result.check_tools, f"package.json:{name}")
        if any(keyword in lowered for keyword in AUTO_FIX_KEYWORDS):
            _append_unique(result.auto_fix_evidence, f"package.json:{name}")
    if "lint:fix" in scripts or "format" in scripts or "format:write" in scripts:
        _append_unique(result.auto_fix_evidence, "package.json scripts")


def _detect_from_workflows(root: Path, result: StaticAnalysisResult) -> None:
    workflow_dir = root / ".github" / "workflows"
    if not workflow_dir.exists():
        return
    files = list(workflow_dir.glob("*.yml")) + list(workflow_dir.glob("*.yaml"))
    for path in files:
        data = _safe_load_yaml(path)
        text = _safe_read_text(path)
        lowered = (" ".join(_collect_strings(data)) + " " + text).lower()
        for keyword in CHECK_KEYWORDS:
            if keyword in lowered:
                _append_unique(
                    result.check_tools,
                    f"{path.relative_to(root)}:{keyword}",
                )
        for keyword in AUTO_FIX_KEYWORDS:
            if keyword in lowered:
                _append_unique(
                    result.auto_fix_evidence,
                    f"{path.relative_to(root)}:{keyword}",
                )
        for keyword in AI_REVIEW_KEYWORDS:
            if keyword in lowered:
                _append_unique(
                    result.ai_review_signals,
                    f"{path.relative_to(root)}:{keyword}",
                )


def scan_repository(
    root: Path,
    documentation_refs: list[str] | None = None,
) -> StaticAnalysisResult:
    result = StaticAnalysisResult()
    _detect_from_root_files(root, result)
    _parse_pyproject_signals(root, result)
    _detect_from_requirements(root, result)
    _detect_from_shell_scripts(root, result)
    _detect_from_package_json(root, result)
    _detect_from_workflows(root, result)
    result.container_environment = _scan_container_environment(root)
    documentation = _scan_markdown_docs(root)
    for ref in documentation_refs or []:
        documentation = _merge_documentation_assessments(
            documentation,
            _scan_markdown_docs_from_git_ref(root, ref),
        )
    result.documentation = documentation

    for parser in (
        _parse_ruff_rule_count,
        _parse_golangci_rule_count,
        _parse_pre_commit_hooks,
        _parse_eslint_rule_count,
        _parse_checkstyle_rule_count,
        _parse_package_json_rule_count,
    ):
        detail = parser(root)
        if detail is not None:
            result.rule_count_details.append(detail)
            if detail.count is not None:
                result.rule_count_estimate += detail.count

    result.style_defined = bool(result.style_evidence)
    result.code_check_supported = bool(result.check_tools or result.rule_count_details)
    result.auto_fix_supported = bool(result.auto_fix_evidence)
    result.check_tools = sorted(set(result.check_tools))
    return result


def infer_local_commands(root: Path, result: StaticAnalysisResult) -> None:
    container = result.container_environment
    if container.defined:
        _append_unique(
            result.inference_evidence,
            f"container strategy: {container.preferred_strategy}",
        )
        if container.setup_supported_locally:
            _append_unique(
                result.inference_evidence,
                "container environment can be prepared locally",
            )
        elif container.note:
            _append_unique(
                result.inference_evidence,
                f"container environment note: {container.note}",
            )

    if result.documentation.markdown_files_scanned:
        _append_unique(
            result.inference_evidence,
            f"markdown scanned: {result.documentation.markdown_files_scanned} files",
        )

    if (root / "build" / "build.sh").exists():
        result.inferred_build_command = "bash build/build.sh"
        _append_unique(result.inference_evidence, "build/build.sh detected")
    if (root / "tests" / "run_UT_test.sh").exists():
        result.inferred_unit_test_command = "bash tests/run_UT_test.sh"
        _append_unique(result.inference_evidence, "tests/run_UT_test.sh detected")
    elif (root / "tests" / "run_test.sh").exists():
        result.inferred_unit_test_command = "bash tests/run_test.sh"
        _append_unique(result.inference_evidence, "tests/run_test.sh detected")

    package_json = root / "package.json"
    if package_json.exists():
        data = _safe_load_json(package_json)
        scripts = data.get("scripts", {}) if isinstance(data, dict) else {}
        if isinstance(scripts, dict):
            if scripts.get("build") and not result.inferred_build_command:
                result.inferred_build_command = "npm run build"
                _append_unique(result.inference_evidence, "package.json:scripts.build")
            if scripts.get("test") and not result.inferred_unit_test_command:
                result.inferred_unit_test_command = "npm test"
                _append_unique(result.inference_evidence, "package.json:scripts.test")
            for key in ("lint", "check"):
                if scripts.get(key) and not result.inferred_code_check_command:
                    result.inferred_code_check_command = f"npm run {key}"
                    _append_unique(
                        result.inference_evidence, f"package.json:scripts.{key}"
                    )
                    break

    if (root / "go.mod").exists() and not (
        result.inferred_build_command
        or result.inferred_unit_test_command
        or result.inferred_code_check_command
    ):
        result.inferred_build_command = "go build ./..."
        result.inferred_unit_test_command = "go test ./..."
        result.inferred_code_check_command = "golangci-lint run"
        result.inference_evidence.extend(["go.mod", "Go default commands"])

    if (root / "Cargo.toml").exists() and not (
        result.inferred_build_command
        or result.inferred_unit_test_command
        or result.inferred_code_check_command
    ):
        result.inferred_build_command = "cargo build"
        result.inferred_unit_test_command = "cargo test"
        result.inferred_code_check_command = (
            "cargo clippy --all-targets --all-features -- -D warnings"
        )
        result.inference_evidence.extend(["Cargo.toml", "Rust default commands"])

    gradlew = "gradlew.bat" if (root / "gradlew.bat").exists() else "./gradlew"
    if (
        (root / "build.gradle").exists() or (root / "build.gradle.kts").exists()
    ) and not (
        result.inferred_build_command
        or result.inferred_unit_test_command
        or result.inferred_code_check_command
    ):
        result.inferred_build_command = f"{gradlew} build -x test"
        result.inferred_unit_test_command = f"{gradlew} test"
        result.inferred_code_check_command = f"{gradlew} check"
        result.inference_evidence.extend(["Gradle build file", gradlew])

    if (root / "pom.xml").exists() and not (
        result.inferred_build_command
        or result.inferred_unit_test_command
        or result.inferred_code_check_command
    ):
        result.inferred_build_command = "mvn -q -DskipTests package"
        result.inferred_unit_test_command = "mvn -q test"
        result.inferred_code_check_command = "mvn -q verify -DskipTests"
        result.inference_evidence.extend(["pom.xml", "Maven default commands"])

    if (
        (root / "pytest.ini").exists() or (root / "tests").exists()
    ) and not result.inferred_unit_test_command:
        result.inferred_unit_test_command = "pytest -q"
        result.inference_evidence.append("tests/ or pytest.ini detected")

    if (
        root / ".pre-commit-config.yaml"
    ).exists() and not result.inferred_code_check_command:
        result.inferred_code_check_command = "pre-commit run -a"
        _append_unique(result.inference_evidence, ".pre-commit-config.yaml detected")
    elif (root / "pyproject.toml").exists() and not result.inferred_code_check_command:
        pyproject_text = _safe_read_text(root / "pyproject.toml").lower()
        if "tool.ruff" in pyproject_text:
            result.inferred_code_check_command = "ruff check ."
            _append_unique(
                result.inference_evidence, "pyproject.toml:tool.ruff detected"
            )

    documented_build = _select_documented_command(result.documentation, "build")
    documented_test = _select_documented_command(result.documentation, "test")
    documented_check = _select_documented_command(result.documentation, "check")

    if documented_build and not result.inferred_build_command:
        result.inferred_build_command = documented_build.command
        _append_unique(
            result.inference_evidence,
            f"documented build command: {documented_build.source_file}",
        )
    if documented_test and not result.inferred_unit_test_command:
        result.inferred_unit_test_command = documented_test.command
        _append_unique(
            result.inference_evidence,
            f"documented test command: {documented_test.source_file}",
        )
    if documented_check and not result.inferred_code_check_command:
        result.inferred_code_check_command = documented_check.command
        _append_unique(
            result.inference_evidence,
            f"documented code-check command: {documented_check.source_file}",
        )
