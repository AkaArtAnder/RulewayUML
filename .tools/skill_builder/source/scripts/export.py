#!/usr/bin/env python3
"""Экспорт в контейнере: исходники, SVG, развёрнутый PlantUML и HTML."""

import argparse
import hashlib
import html
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from urllib.parse import quote
import xml.etree.ElementTree as ET


def runtime_settings():
    skill = Path(__file__).resolve().parent.parent
    # В пакете лежит копия Dockerfile проекта; последний путь — монтирование export.sh.
    candidates = (skill / "assets/runtime/Dockerfile", Path("/runtime/Dockerfile"))
    dockerfile = next((path for path in candidates if path.is_file()), None)
    if dockerfile is None:
        raise ValueError("Не найден Dockerfile окружения. Используйте полный пакет скилла.")
    text = dockerfile.read_text(encoding="utf-8")
    versions = re.findall(r"(?m)^ARG PLANTUML_VERSION=(\d+\.\d+\.\d+)\s*$", text)
    limits = re.findall(r"(?m)^ENV PLANTUML_LIMIT_SIZE=([1-9]\d*)\s*$", text)
    if len(versions) != 1 or len(limits) != 1:
        raise ValueError("В Dockerfile нужны однозначные PLANTUML_VERSION и PLANTUML_LIMIT_SIZE.")
    return {"plantuml_version": versions[0], "docker_image": f"rulewayuml-dev:plantuml-{versions[0]}", "limit_size": limits[0]}


def checked_path(root, value):
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts or relative == Path("."):
        raise ValueError(f"Нужен относительный путь внутри рабочего каталога: {value}")
    candidate = root / relative
    resolved = candidate.resolve(strict=True)
    if not resolved.is_relative_to(root):
        raise ValueError(f"Путь выходит за рабочий каталог: {value}")
    return relative, candidate


def copy_item(source, destination, root):
    if not source.resolve(strict=True).is_relative_to(root):
        raise ValueError(f"Ссылка выходит за рабочий каталог: {source}")
    if source.is_dir():
        # Ссылки на каталоги отклоняются, чтобы избежать циклов при переносе.
        if source.is_symlink():
            raise ValueError(f"Замените ссылку на каталог обычным каталогом: {source}")
        destination.mkdir(parents=True, exist_ok=True)
        for item in source.iterdir():
            copy_item(item, destination / item.name, root)
    elif source.is_file():
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists():
            if destination.read_bytes() != source.read_bytes():
                raise ValueError(f"Конфликт файлов в комплекте: {destination}")
        else:
            shutil.copyfile(source, destination)
    else:
        raise ValueError(f"Нужен обычный файл или каталог: {source}")


def plantuml(source, mode, runtime):
    environment = dict(os.environ, PLANTUML_LIMIT_SIZE=runtime["limit_size"])
    completed = subprocess.run(
        ["plantuml", "-charset", "UTF-8", "-pipe", "-filename", source.name, mode],
        input=source.read_bytes(), cwd=source.parent, env=environment, capture_output=True, timeout=120,
    )
    if completed.returncode:
        # Не публикуем получившееся изображение ошибки как готовый SVG.
        diagnostic = completed.stderr.decode("utf-8", errors="replace").strip()
        raise ValueError(f"PlantUML: ошибка {completed.returncode} в {source.name}. {diagnostic}")
    return completed.stdout


def url_path(path):
    return html.escape(quote(path, safe="/"), quote=True)


def render(source, relative, stage, runtime):
    text = source.read_text(encoding="utf-8-sig")
    if len(re.findall(r"(?m)^\s*@startuml\b", text)) != 1 or len(re.findall(r"(?m)^\s*@enduml\b", text)) != 1:
        raise ValueError(f"Ожидается одна самостоятельная схема @startuml в {relative}")
    target = stage / "diagrams" / relative.with_suffix(".svg")
    target.parent.mkdir(parents=True, exist_ok=True)
    portable = target.with_name(target.stem + "_portable.puml")
    page = target.with_suffix(".html")
    for file in (target, portable, page):
        if file.exists():
            raise ValueError(f"Результат конфликтует с предоставленным материалом: {file.name}")

    svg = plantuml(source, "-tsvg", runtime)
    root = ET.fromstring(svg)
    if root.tag != "{http://www.w3.org/2000/svg}svg" or not root.get("viewBox"):
        raise ValueError(f"PlantUML не вернул полноценный SVG: {relative}")
    _, _, width, height = map(float, root.get("viewBox").split())
    if not all(math.isfinite(value) and value > 0 for value in (width, height)):
        raise ValueError(f"Некорректные размеры SVG: {relative}")
    expanded = plantuml(source, "-preproc", runtime)
    if re.search(rb"(?mi)^\s*!include", expanded) or b"@startuml" not in expanded:
        raise ValueError(f"Не удалось получить исходник без подключений: {relative}")
    if list(root.iter("{http://www.w3.org/2000/svg}image")):
        raise ValueError(f"В {relative} обнаружена вставка изображения; для совместимости с Wiki используйте векторный SVG-спрайт из контуров.")
    if any(tag in "".join(root.itertext()) for tag in ("<center>", "<left>")):
        raise ValueError(f"В {relative} остались несовместимые теги выравнивания. Обновите components/.")
    target.write_bytes(svg)
    portable.write_bytes(expanded)

    title = html.escape(relative.stem)
    svg_url = url_path(target.name)
    source_url = url_path(os.path.relpath(source, page.parent))
    portable_url = url_path(portable.name)
    page.write_text(f'''<!doctype html>
<html lang="ru">
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
body {{ margin: 0; padding: 20px; font-family: sans-serif; color: #142d3b; background: #f5f8f7; }}
nav {{ display: flex; flex-wrap: wrap; gap: 16px; margin-bottom: 16px; }}
a {{ color: #087f74; }}
object {{ display: block; width: min(100%, {width:g}px); height: auto; aspect-ratio: {width:g} / {height:g}; background: white; }}
</style>
<nav aria-label="Файлы схемы">
<a href="{svg_url}">Открыть SVG</a>
<a href="{source_url}">Редактируемый исходник</a>
<a href="{portable_url}">Код для вставки</a>
</nav>
<object data="{svg_url}" type="image/svg+xml" aria-label="{title}">
<a href="{svg_url}">Открыть схему отдельным файлом</a>
</object>
</html>
''', encoding="utf-8")
    return {
        "source": source.relative_to(stage).as_posix(),
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "svg": target.relative_to(stage).as_posix(),
        "html": page.relative_to(stage).as_posix(),
        "portable_source": portable.relative_to(stage).as_posix(),
    }


def export(args):
    if not Path("/.dockerenv").exists():
        raise ValueError("Запускайте экспорт через export.sh или внутри Docker / Dev Container.")
    runtime = runtime_settings()
    version = runtime["plantuml_version"]
    banner = subprocess.check_output(["plantuml", "-version"], text=True, timeout=30)
    if not re.search(rf"PlantUML version {re.escape(version)}(?:\s|$)", banner):
        raise ValueError(f"Для RulewayUML требуется PlantUML {version}; фактическая версия: {banner.splitlines()[0]}. Используйте образ {runtime['docker_image']}.")
    workspace = Path(args.workspace).resolve(strict=True)
    output = Path(args.output).absolute()
    if output.exists() or output.is_symlink():
        raise ValueError("Каталог результата уже существует. Выберите новый каталог.")
    files = [checked_path(workspace, value) for value in args.files]
    if any(not path.is_file() or relative.suffix.lower() != ".puml" for relative, path in files):
        raise ValueError("Передайте самостоятельные файлы .puml.")
    if len({relative for relative, _ in files}) != len(files):
        raise ValueError("Один исходник указан несколько раз.")
    assets = [checked_path(workspace, value) for value in args.asset]
    library = workspace / "components"
    for directory in [library] + [path for _, path in assets if path.is_dir()]:
        if output.resolve().is_relative_to(directory.resolve()):
            raise ValueError("Каталог результата не должен находиться внутри копируемых ресурсов.")
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=".ruleway_export_", dir=output.parent))
    try:
        if library.exists():
            copy_item(library, stage / "source/components", workspace)
        for relative, path in files + assets:
            copy_item(path, stage / "source" / relative, workspace)
        for relative, path in assets:
            copy_item(path, stage / "diagrams" / relative, workspace)
        records = [render(stage / "source" / relative, relative, stage, runtime) for relative, _ in files]
        manifest = {"plantuml": version, "limit_size": int(runtime["limit_size"]), "diagrams": records}
        (stage / "export_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if output.exists() or output.is_symlink():
            raise ValueError("Каталог результата появился во время экспорта; он сохранён.")
        stage.rename(output)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    print(f"Экспортировано схем: {len(files)}. Комплект: {output}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workspace")
    parser.add_argument("output")
    parser.add_argument("files", nargs="+")
    parser.add_argument("--asset", action="append", default=[], help="Предоставленный локальный материал, относительно рабочего каталога")
    args = parser.parse_args()
    try:
        export(args)
    except (ValueError, OSError, subprocess.SubprocessError, ET.ParseError) as error:
        print(f"Экспорт не выполнен: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
