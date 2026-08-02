import os
import sys
import subprocess
import pytest


def run_import(src, dst, allow_writes=False):
    cmd = [sys.executable, "elodie.py", "import", "--source", src, "--destination", dst]
    if allow_writes:
        cmd.append("--allow-metadata-writes")
    subprocess.run(cmd, check=True)


def test_import_no_duplicates(tmp_path):
    src = tmp_path / "src"
    dst = tmp_path / "dst"
    src.mkdir()
    dst.mkdir()
    (src / "photo.txt").write_text("hello")

    run_import(str(src), str(dst), allow_writes=False)

    files = [p.name for p in dst.rglob("*") if p.is_file()]
    assert not any(name.endswith("_original") for name in files)


def test_import_with_duplicates_allowed(tmp_path):
    src = tmp_path / "src2"
    dst = tmp_path / "dst2"
    src.mkdir()
    dst.mkdir()
    (src / "photo.txt").write_text("hello")

    run_import(str(src), str(dst), allow_writes=True)

    files = [p.name for p in dst.rglob("*") if p.is_file()]
    assert any(name.endswith("_original") for name in files)
