from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

from oss_issue_fixer.repo_eval_input import load_repos_from_xlsx


def test_load_repos_from_xlsx_reads_repo_url_column(tmp_path: Path):
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "sheet1"
    sheet.append(["组织名", "项目名", "仓库名", "仓库链接"])
    sheet.append(["Ascend", "MindIE", "MindIE-SD", "https://gitcode.com/Ascend/MindIE-SD.git"])
    sheet.append(["vLLM", "vLLM", "vllm", "https://github.com/vllm-project/vllm.git"])
    sheet.append(["vLLM", "vLLM", "vllm", "https://github.com/vllm-project/vllm.git"])
    xlsx_path = tmp_path / "repos.xlsx"
    workbook.save(xlsx_path)

    repos = load_repos_from_xlsx(str(xlsx_path))

    assert repos == [
        "https://gitcode.com/Ascend/MindIE-SD.git",
        "https://github.com/vllm-project/vllm.git",
    ]
