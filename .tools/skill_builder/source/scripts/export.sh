#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 3 || "${1:-}" == --* ]]; then
    echo 'Использование: bash export.sh РАБОЧИЙ_КАТАЛОГ НОВЫЙ_КАТАЛОГ_РЕЗУЛЬТАТА файл.puml [файл.puml ...] [--asset путь]' >&2
    exit 2
fi
skill_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
runtime_file="$skill_dir/assets/runtime/Dockerfile"
if [[ ! -f "$runtime_file" ]]; then echo 'Не найден Dockerfile. Используйте полный пакет скилла.' >&2; exit 1; fi
runtime_file="$(cd "$(dirname "$runtime_file")" && pwd)/Dockerfile"
version="$(sed -n 's/^ARG PLANTUML_VERSION=//p' "$runtime_file")"
if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then echo 'Некорректная версия PlantUML в Dockerfile.' >&2; exit 1; fi
input_dir="$(cd "$1" && pwd)"
output_arg="$2"
shift 2

if [[ -f /.dockerenv ]]; then
    exec python3 "$skill_dir/scripts/export.py" "$input_dir" "$output_arg" "$@"
fi

command -v docker >/dev/null || { echo 'Для экспорта нужен Docker или Dev Container.' >&2; exit 1; }
renderer_image="${RULEWAY_IMAGE:-rulewayuml-dev:plantuml-$version}"
docker image inspect "$renderer_image" >/dev/null 2>&1 || {
    echo "Образ $renderer_image недоступен. Порядок сборки: references/export.md." >&2
    exit 1
}
if [[ -e "$output_arg" || -L "$output_arg" ]]; then
    echo 'Каталог результата уже существует. Выберите новый, чтобы сохранить предыдущую редакцию.' >&2
    exit 1
fi
mkdir -p "$(dirname "$output_arg")"
output_parent="$(cd "$(dirname "$output_arg")" && pwd)"
output_dir="$output_parent/$(basename "$output_arg")"
stage_dir="$(mktemp -d "$output_parent/.ruleway_export.XXXXXX")"
trap 'rm -rf "$stage_dir"' EXIT
docker run --rm --network none --user "$(id -u):$(id -g)" \
    --mount "type=bind,src=$skill_dir,dst=/skill,readonly" \
    --mount "type=bind,src=$runtime_file,dst=/runtime/Dockerfile,readonly" \
    --mount "type=bind,src=$input_dir,dst=/input,readonly" \
    --mount "type=bind,src=$stage_dir,dst=/output" \
    --entrypoint python3 "$renderer_image" \
    /skill/scripts/export.py /input /output/result "$@"
if [[ -e "$output_dir" || -L "$output_dir" ]]; then
    echo 'Каталог результата появился во время экспорта; предыдущие файлы сохранены.' >&2
    exit 1
fi
mv "$stage_dir/result" "$output_dir"
printf 'Комплект создан: %s\n' "$output_dir"
