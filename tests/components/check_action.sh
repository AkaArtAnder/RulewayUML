#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f /.dockerenv ]]; then
    printf '%s\n' 'Запускайте проверку только внутри Docker / Dev Container.' >&2
    exit 1
fi

source_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_dir="$(cd "$source_dir/../.." && pwd)"
output_dir="${1:-/tmp/rulewayuml-action-results}"
mkdir -p "$output_dir"
output_dir="$(cd "$output_dir" && pwd)"
work_dir="$(mktemp -d /tmp/rulewayuml-action.XXXXXX)"
trap 'rm -rf "$work_dir"' EXIT
inputs=("$repo_dir"/examples/*.puml "$source_dir"/*.puml)

plantuml -version
plantuml -charset UTF-8 -checkonly "${inputs[@]}"
for format in svg png; do
    plantuml -charset UTF-8 -failfast2 -t"$format" -o "$output_dir" "${inputs[@]}"
done
cp -r "$repo_dir/examples/materials" "$output_dir/"

# VS Code передаёт исходник через stdin и задаёт каталог include отдельно.
# Проверяем тот же JAR, который выбран в .vscode/settings.json.
for format in svg png; do
    java -Dplantuml.include.path="$source_dir" -Djava.awt.headless=true \
        -jar /opt/plantuml/plantuml.jar -pipeimageindex 0 -charset UTF-8 \
        -pipe -t"$format" -filename action_content.puml \
        < "$source_dir/action_content.puml" > "$output_dir/action_content_preview.$format"
done

# Подключается только копия components/: без docs/, examples/ и рабочего каталога репозитория.
portable_dir="$work_dir/copy with spaces"
mkdir -p "$portable_dir"
cp -r "$repo_dir/components" "$portable_dir/"
cat > "$portable_dir/portable.puml" <<'PUML'
@startuml
!include components/action.puml
start
$ruleway_action("РПЕ-01", "Перенос библиотеки", "Автор", "Подключение работает")
stop
@enduml
PUML
(
    cd /
    plantuml -charset UTF-8 -checkonly "$portable_dir/portable.puml"
    plantuml -charset UTF-8 -failfast2 -tsvg -o "$output_dir" "$portable_dir/portable.puml"
    plantuml -charset UTF-8 -failfast2 -tpng -o "$output_dir" "$portable_dir/portable.puml"
)

# Ошибки должны отклоняться проверкой параметров, а не случайной синтаксической ошибкой.
reject() {
    local name="$1" call="$2" status
    printf '@startuml\n!include %s/components/action.puml\nstart\n%s\nstop\n@enduml\n' \
        "$repo_dir" "$call" > "$work_dir/$name.puml"
    if plantuml -charset UTF-8 -pipe -syntax < "$work_dir/$name.puml" > "$output_dir/$name.log" 2>&1; then
        printf 'ОШИБКА: принят некорректный случай %s\n' "$name" >&2
        exit 1
    else
        status=$?
    fi
    if [[ $status != 200 || $(< "$output_dir/$name.log") != *'Assertion error : Ruleway:'* ]]; then
        cat "$output_dir/$name.log" >&2
        printf 'ОШИБКА: случай %s отклонён не проверкой Ruleway\n' "$name" >&2
        exit 1
    fi
    printf '%s: ожидаемая ошибка Ruleway, код %s\n' "$name" "$status"
}
reject invalid_prefix '$ruleway_action("PСТ-03", "Действие", "Автор", "Итог")'
reject invalid_number '$ruleway_action("РСТ-AA", "Действие", "Автор", "Итог")'
reject short_number '$ruleway_action("РСТ-3", "Действие", "Автор", "Итог")'
reject empty_name '$ruleway_action("РСТ-03", "", "Автор", "Итог")'
reject empty_responsible '$ruleway_action("РСТ-03", "Действие", "", "Итог")'
reject empty_result '$ruleway_action("РСТ-03", "Действие", "Автор", "")'

java -Djava.awt.headless=true "$source_dir/verify_action.java" "$output_dir"
printf 'Проверка действия пройдена. Результаты: %s\n' "$output_dir"
