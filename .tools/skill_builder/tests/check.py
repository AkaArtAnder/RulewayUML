#!/usr/bin/env python3
"""Проверить переносимость пакета и поведение нового экспортёра в контейнере."""

import hashlib
import html.parser
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import zipfile
from urllib.parse import unquote
import xml.etree.ElementTree as ET


def run(command, success=True, **options):
    result = subprocess.run(command, capture_output=True, text=True, **options)
    if (result.returncode == 0) != success:
        raise AssertionError(f"Неожиданный код {result.returncode}: {command}\n{result.stdout}\n{result.stderr}")
    return result


def main():
    assert Path("/.dockerenv").exists(), "Проверка выполняется только в контейнере"
    builder = Path(__file__).resolve().parents[1]
    repo = builder.parent.parent
    work = Path(sys.argv[1]).resolve()
    assert work.is_relative_to(Path("/tmp")), "Распакованные проверки размещаются только в /tmp контейнера"
    work.mkdir(parents=True, exist_ok=False)
    build = work / "package with spaces"
    run(["python3", str(builder / "build.py"), str(build)])
    archives = list(build.glob("rulewayuml-*.zip"))
    assert len(archives) == 1
    with zipfile.ZipFile(archives[0]) as archive:
        archive.extractall(build)
    skill = build / "rulewayuml"
    manifest = json.loads((skill / "package_manifest.json").read_text())
    runtime = manifest["runtime"]
    suffix = "_portable"
    for relative, digest in manifest["sha256"].items():
        assert hashlib.sha256((skill / relative).read_bytes()).hexdigest() == digest, relative
    for component in (repo / "components").rglob("*"):
        if component.is_file():
            assert component.read_bytes() == (skill / "assets/components" / component.relative_to(repo / "components")).read_bytes()
    for doc in skill.rglob("*.md"):
        for link in re.findall(r"\]\(([^)]+)\)", doc.read_text()):
            if re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", link) or link.startswith("#"):
                continue
            assert (doc.parent / link.split("#", 1)[0]).exists(), (doc, link)
    print("Пакет: независимые ресурсы, ссылки справочников и контрольные суммы совпадают.")

    # Экспортируем копию вне репозитория: компоненты и пути должны быть самодостаточны.
    inputs = work / "рабочий каталог"
    shutil.copytree(skill / "assets", inputs)
    special = inputs / "examples/Схема #1 & проверка.puml"
    special.write_bytes((inputs / "examples/parallel_results.puml").read_bytes())
    relative_files = [file.relative_to(inputs).as_posix() for file in sorted((inputs / "examples").glob("*.puml"))]
    export_script = str(skill / "scripts/export.sh")
    export_command = ["bash", export_script]
    output = work / "export"
    run([*export_command, str(inputs), str(output), *relative_files, "--asset", "examples/materials"])
    exported = json.loads((output / "export_manifest.json").read_text())
    assert len(exported["diagrams"]) == 9
    assert "target" not in exported and exported["plantuml"] == runtime["plantuml_version"]
    assert exported["limit_size"] == 4096
    for record in exported["diagrams"]:
        source = output / record["source"]
        relative = source.relative_to(output / "source")
        assert source.read_bytes() == (inputs / relative).read_bytes()
        assert hashlib.sha256(source.read_bytes()).hexdigest() == record["source_sha256"]
        root = ET.parse(output / record["svg"]).getroot()
        assert not list(root.iter("{http://www.w3.org/2000/svg}image")), record
        assert len(list(root.iter("{http://www.w3.org/2000/svg}path"))) >= 134, record
        assert "<center>" not in "".join(root.itertext()) and "<left>" not in "".join(root.itertext()), record
        assert (output / record["html"]).is_file()
        portable_text = (output / record["portable_source"]).read_text()
        assert not re.search(r"(?m)^\s*!include", portable_text)
        assert len(re.findall(r"(?m)^sprite ruleway_logo ", portable_text)) == 1, "Знак должен определяться один раз"
        assert record["portable_source"].endswith(suffix + ".puml")

    ns = {"svg": "http://www.w3.org/2000/svg"}
    svg_path = output / "diagrams/examples/subregulation_result.svg"
    root = ET.parse(svg_path).getroot()
    hrefs = [node.get("{http://www.w3.org/1999/xlink}href", node.get("href")) for node in root.findall(".//svg:a", ns)]
    assert "subregulation_review.svg" in hrefs, hrefs
    assert (svg_path.parent / "subregulation_review.svg").is_file()
    assert (output / "diagrams/examples/materials/review_template.html").is_file()
    assert "1 рабочий день" in " ".join(" ".join(root.itertext()).split())

    class Links(html.parser.HTMLParser):
        def __init__(self):
            super().__init__()
            self.paths = []

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if tag == "object":
                assert attrs["type"] == "image/svg+xml"
                self.paths.append(attrs["data"])
            elif tag == "a":
                self.paths.append(attrs["href"])

    page = output / "diagrams/examples/Схема #1 & проверка.html"
    links = Links()
    links.feed(page.read_text())
    assert len(links.paths) == 5
    for url in links.paths:
        assert "#" not in url and " " not in url
        assert (page.parent / unquote(url)).is_file(), url
    print("Экспорт: 9 схем, кириллица и специальные символы в путях, знак, SLA и адреса сохранены.")

    # Развёрнутый исходник должен отрисовываться без библиотечных файлов.
    detached = work / "detached"
    detached.mkdir()
    portable = output / ("diagrams/examples/subregulation_result" + suffix + ".puml")
    moved = detached / "paste.puml"
    moved.write_bytes(portable.read_bytes())
    result = run(["plantuml", "-charset", "UTF-8", "-tsvg", "-pipe"], input=moved.read_text(), cwd=detached)
    rebuilt = ET.fromstring(result.stdout)
    assert list(root.itertext()) == list(rebuilt.itertext())
    print("Код для вставки отрисован отдельно без components/, текст схемы совпадает.")

    # Перенос полного комплекта сохраняет редактируемые include и связанные материалы.
    relocated = work / "relocated"
    shutil.copytree(output, relocated)
    run([*export_command, str(relocated / "source"), str(work / "reexport"),
         "examples/subregulation_result.puml", "examples/subregulation_review.puml"])
    sentinel = output / "keep.txt"
    sentinel.write_text("Предыдущая редакция")
    run([*export_command, str(inputs), str(output), "examples/parallel_results.puml"], success=False)
    assert sentinel.read_text() == "Предыдущая редакция"
    invalid = inputs / "invalid.puml"
    invalid.write_text('@startuml\n!include components/action.puml\nstart\n$ruleway_action("РТС-01", "Проверить", "Автор", "")\nstop\n@enduml\n')
    failure = work / "failed"
    result = run([*export_command, str(inputs), str(failure), "examples/parallel_results.puml", "invalid.puml"], success=False)
    assert not failure.exists(), "Частичный комплект не должен публиковаться"
    assert "ошибка 200" in result.stderr, result.stderr
    assert not list(work.glob(".ruleway_export_*")), "Временные результаты должны удаляться"
    missing = inputs / "missing.puml"
    missing.write_text('@startuml\n!include absent.puml\nstart\nstop\n@enduml\n')
    run([*export_command, str(inputs), str(failure), "missing.puml"], success=False)
    assert not failure.exists()
    raster = inputs / "raster.puml"
    raster.write_text('@startuml\nsprite ruleway_test {\nFF\nFF\n}\nnote "<$ruleway_test>" as N\n@enduml\n')
    rejected = run([*export_command, str(inputs), str(failure), "raster.puml"], success=False)
    assert "вставка изображения" in rejected.stderr and not failure.exists(), rejected.stderr
    tags = inputs / "tags.puml"
    tags.write_text('@startuml\nnote "<center>Текст" as N\n@enduml\n')
    rejected = run([*export_command, str(inputs), str(failure), "tags.puml"], success=False)
    assert "теги выравнивания" in rejected.stderr and not failure.exists(), rejected.stderr
    print("Wiki: растровые вставки и несовместимые теги отклоняются без частичного результата.")
    print("Повторный экспорт после переноса работает; существующий каталог и исходники сохранены, ошибки не оставляют SVG.")
    print(f"Все проверки единого экспортёра пройдены. Результаты: {work}")


if __name__ == "__main__":
    main()
