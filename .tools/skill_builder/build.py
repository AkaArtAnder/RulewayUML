#!/usr/bin/env python3
"""Собрать самодостаточный пакет скилла из текущих файлов библиотеки."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import shutil
import tempfile
import zipfile


def build(destination):
    if not Path("/.dockerenv").exists():
        raise ValueError("Собирайте пакет внутри Docker / Dev Container.")
    builder = Path(__file__).resolve().parent
    repo = builder.parent.parent
    if destination.resolve().is_relative_to(builder):
        raise ValueError("Каталог сборки должен находиться вне исходников скилла.")
    version_match = re.search(r'^  version: "(\d+\.\d+\.\d+)"$', (builder / "source/skill_template.md").read_text(), re.M)
    if version_match is None:
        raise ValueError("В шаблоне нужна версия пакета в формате X.Y.Z без суффикса.")
    version = version_match.group(1)
    destination.mkdir(parents=True, exist_ok=True)
    archive_path = destination / f"rulewayuml-{version}.zip"
    if archive_path.exists() or archive_path.is_symlink():
        raise ValueError("Архив уже существует; выберите другой каталог для новой сборки.")
    # Распакованный скилл существует только во временном каталоге контейнера.
    stage = Path(tempfile.mkdtemp(prefix="ruleway_package_", dir="/tmp"))
    try:
        package = stage / "rulewayuml"
        shutil.copytree(builder / "source", package, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        (package / "skill_template.md").rename(package / "SKILL.md")
        shutil.copytree(repo / "components", package / "assets/components")
        examples = package / "assets/examples"
        examples.mkdir(parents=True)
        for name in ("basic_regulation", "basic_regulation_no_lanes", "review_regulation"):
            shutil.copyfile(repo / f"examples/{name}.puml", examples / f"{name}.puml")
        shutil.copytree(repo / "examples/materials", examples / "materials")
        for source in sorted((builder / "scenarios").glob("*.puml")):
            text = source.read_text().replace("!include ../../../components/", "!include ../components/")
            (examples / source.name).write_text(text, encoding="utf-8")
        details = (builder / "scenarios/README.md").read_text()
        details = details.split("## Состав\n", 1)[1].split("## Как использовать при подготовке скилла", 1)[0]
        for example in examples.glob("*.puml"):
            details = details.replace(f"]({example.name})", f"](../assets/examples/{example.name})")
        details = details.replace("рассчитаны на их положение в репозитории", "рассчитаны на положение в assets/examples/ пакета")
        (package / "references/route_details.md").write_text(
            "# Сложные маршруты: предпосылки и ожидаемые пути\n\n"
            "Отображение исходных образцов подтверждено владельцем библиотеки. "
            "Предметные данные учебные; таблицы задают ожидаемые маршруты.\n\n## Состав\n" + details,
            encoding="utf-8",
        )
        runtime = package / "assets/runtime"
        runtime.mkdir()
        shutil.copyfile(repo / ".devcontainer/Dockerfile", runtime / "Dockerfile")
        checksum = {}
        for file in sorted(package.rglob("*")):
            if file.is_file():
                checksum[file.relative_to(package).as_posix()] = hashlib.sha256(file.read_bytes()).hexdigest()
        settings = runpy.run_path(str(package / "scripts/export.py"))["runtime_settings"]()
        (package / "package_manifest.json").write_text(json.dumps({
            "version": version, "runtime": settings, "sha256": checksum,
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        with zipfile.ZipFile(stage / f"rulewayuml-{version}.zip", "w", zipfile.ZIP_DEFLATED) as archive:
            for file in sorted(package.rglob("*")):
                if file.is_file():
                    archive.write(file, file.relative_to(stage))
        # Публикуем только законченный ZIP; существующий архив не заменяем даже при гонке.
        with tempfile.NamedTemporaryFile(prefix=".ruleway_archive_", dir=destination) as pending:
            with (stage / archive_path.name).open("rb") as stream:
                shutil.copyfileobj(stream, pending)
            pending.flush()
            os.fchmod(pending.fileno(), 0o644)
            os.link(pending.name, archive_path)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    print(f"ZIP: {archive_path}")
    return archive_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path, help="Каталог для ZIP; распакованный пакет создаётся временно в /tmp")
    options = parser.parse_args()
    try:
        build(options.output.absolute())
    except (OSError, ValueError) as error:
        parser.exit(1, f"Сборка не выполнена: {error}\n")
