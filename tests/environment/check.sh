#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f /.dockerenv ]]; then
    printf '%s\n' 'Запускайте эту проверку только внутри Docker / Dev Container.' >&2
    exit 1
fi

source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
output_dir="${1:-/tmp/rulewayuml-check-results}"
mkdir -p "$output_dir"
output_dir="$(cd "$output_dir" && pwd)"
work_dir="$(mktemp -d /tmp/rulewayuml-input.XXXXXX)"
trap 'rm -rf "$work_dir"' EXIT

# Пробелы в пути проверяют передачу аргументов оболочкой plantuml.
input_dir="$work_dir/input with spaces"
mkdir -p "$input_dir"
cp "$source_dir/step.iuml" "$source_dir/regulation.puml" "$source_dir/graphviz.puml" "$input_dir/"

java -version
plantuml -version
dot -V
plantuml -testdot

plantuml -charset UTF-8 -checkonly "$input_dir/regulation.puml" "$input_dir/graphviz.puml"
plantuml -charset UTF-8 -failfast2 -tsvg -o "$output_dir" "$input_dir/regulation.puml" "$input_dir/graphviz.puml"
plantuml -charset UTF-8 -failfast2 -tpng -o "$output_dir" "$input_dir/regulation.puml" "$input_dir/graphviz.puml"
java -Djava.awt.headless=true "$source_dir/verify_render.java" "$output_dir"

cat > "$input_dir/invalid.puml" <<'PUML'
@startuml
this is not a valid diagram !!!
@enduml
PUML
cat > "$input_dir/missing_include.puml" <<'PUML'
@startuml
!include does_not_exist.iuml
start
:Шаг;
stop
@enduml
PUML

for name in invalid missing_include; do
    if plantuml -charset UTF-8 -checkonly "$input_dir/$name.puml" > "$output_dir/$name.log" 2>&1; then
        printf 'ОШИБКА: некорректный пример %s принят как корректный\n' "$name" >&2
        exit 1
    else
        status=$?
        printf '%s: ожидаемый ненулевой код завершения %s\n' "$name" "$status"
    fi
done

printf 'Проверка окружения пройдена. Результаты: %s\n' "$output_dir"
