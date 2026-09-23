#!/usr/bin/env python3
"""Проверить интерфейс экспортёра с подстановкой вывода PlantUML, без рендеринга схем."""

import hashlib
import html.parser
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from urllib.parse import unquote


def main():
    assert Path("/.dockerenv").exists(), "Проверка выполняется только в контейнере"
    skill = Path(sys.argv[1]).resolve()
    manifest = json.loads((skill / "package_manifest.json").read_text())
    runtime = manifest["runtime"]
    assert runtime["plantuml_version"] == "1.2025.10" and runtime["limit_size"] == "4096"
    assert "export_profiles" not in manifest and not (skill / "config/export_profiles.tsv").exists()
    for relative, digest in manifest["sha256"].items():
        assert hashlib.sha256((skill / relative).read_bytes()).hexdigest() == digest, relative

    with tempfile.TemporaryDirectory(prefix="ruleway_contract_", dir="/tmp") as folder:
        work = Path(folder)
        fake_bin = work / "bin"
        fake_bin.mkdir()
        fake = fake_bin / "plantuml"
        fake.write_text('''#!/usr/bin/env python3
import os, sys
from pathlib import Path
with Path(os.environ["RULEWAY_TEST_CALLS"]).open("a") as log:
    log.write(" ".join(sys.argv[1:]) + "\\n")
if sys.argv[1:] == ["-version"]:
    print("PlantUML version " + os.environ["RULEWAY_TEST_VERSION"])
else:
    assert os.environ["PLANTUML_LIMIT_SIZE"] == "4096"
    sys.stdin.buffer.read()
    mode = os.environ.get("RULEWAY_TEST_FAILURE", "")
    if mode == "renderer":
        print("Подставленная ошибка движка", file=sys.stderr)
        sys.exit(200)
    if "-preproc" in sys.argv:
        print("@startuml\\n' Подставленный результат препроцессора\\n@enduml")
    elif "-tsvg" in sys.argv:
        content = '<text>Подставленный SVG для проверки файлов</text>'
        if mode == "raster": content = '<image href="test.png"/>'
        if mode == "alignment": content = '<text>&lt;center&gt;Текст</text>'
        print('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 20">' + content + '</svg>')
    else:
        sys.exit(99)
''', encoding="utf-8")
        fake.chmod(0o755)
        inputs = work / "исходники с пробелами"
        inputs.mkdir()
        name = "Схема #1 & проверка.puml"
        source = inputs / name
        source.write_text('@startuml\n\' Синтетический вход: PlantUML в этой проверке не запускается.\n@enduml\n', encoding="utf-8")
        original = source.read_bytes()
        (inputs / "components").mkdir()
        (inputs / "components/marker.txt").write_text("Проверка переноса зависимости")
        (inputs / "materials").mkdir()
        (inputs / "materials/file.txt").write_text("Материал пользователя")
        calls = work / "calls.txt"
        environment = dict(os.environ, PATH=f"{fake_bin}:{os.environ['PATH']}",
                           RULEWAY_TEST_CALLS=str(calls), RULEWAY_TEST_VERSION=runtime["plantuml_version"])
        command = ["bash", str(skill / "scripts/export.sh")]

        def run(output, *, error=None, version=None, extra=()):
            env = dict(environment, RULEWAY_TEST_FAILURE=error or "")
            if version is not None:
                env["RULEWAY_TEST_VERSION"] = version
            return subprocess.run([*command, str(inputs), str(output), name, *extra],
                                  env=env, capture_output=True, text=True)

        output = work / "result"
        done = run(output, extra=("--asset", "materials"))
        assert done.returncode == 0, done.stderr
        report = json.loads((output / "export_manifest.json").read_text())
        assert report["plantuml"] == "1.2025.10" and report["limit_size"] == 4096
        assert "target" not in report and len(report["diagrams"]) == 1
        record = report["diagrams"][0]
        assert record["portable_source"] == "diagrams/Схема #1 & проверка_portable.puml"
        assert (output / record["source"]).read_bytes() == original
        assert source.read_bytes() == original
        assert (output / "source/components/marker.txt").exists()
        assert (output / "source/materials/file.txt").exists()
        assert (output / "diagrams/materials/file.txt").exists()
        assert len(list((output / "diagrams").glob("*.puml"))) == 1
        assert len(calls.read_text().splitlines()) == 3, "Один вызов версии, SVG и препроцессора"

        class Links(html.parser.HTMLParser):
            def handle_starttag(self, tag, attrs):
                attributes = dict(attrs)
                key = "data" if tag == "object" else "href" if tag == "a" else None
                if key:
                    assert (output / record["html"]).parent.joinpath(unquote(attributes[key])).is_file()

        Links().feed((output / record["html"]).read_text())
        assert run(output).returncode != 0 and (output / record["source"]).read_bytes() == original
        for failure in ("renderer", "raster", "alignment"):
            destination = work / failure
            result = run(destination, error=failure)
            assert result.returncode != 0 and not destination.exists(), (failure, result.stderr)
        destination = work / "mismatch"
        mismatch = run(destination, version="1.2026.5")
        assert mismatch.returncode != 0 and "требуется PlantUML 1.2025.10" in mismatch.stderr
        assert not destination.exists() and not list(work.glob(".ruleway_export_*"))

        before = calls.read_bytes()
        for executable in (command, ["python3", str(skill / "scripts/export.py")]):
            removed = subprocess.run([*executable, "--target", "yandex-wiki", str(inputs), str(work / "obsolete"), name],
                                     env=environment, capture_output=True, text=True)
            assert removed.returncode != 0 and not (work / "obsolete").exists()
        assert calls.read_bytes() == before, "Удалённый параметр не должен запускать движок"
    print("Проверен единый CLI, состав файлов, перенос зависимостей, ссылки HTML, версия и отказы. PlantUML подставлен; схемы не рендерились.")


if __name__ == "__main__":
    main()
