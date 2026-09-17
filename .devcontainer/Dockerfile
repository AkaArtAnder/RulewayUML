FROM mcr.microsoft.com/devcontainers/java:0-17

ARG PLANTUML_VERSION=1.2026.5

RUN sudo rm -f /etc/apt/sources.list.d/yarn.list \
    && sudo apt-get update \
    && sudo apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        fonts-dejavu \
        graphviz \
        make \
        maven \
    && sudo rm -rf /var/lib/apt/lists/*

RUN sudo mkdir -p /opt/plantuml \
    && sudo curl -fsSL -o /opt/plantuml/plantuml.jar "https://github.com/plantuml/plantuml/releases/download/v${PLANTUML_VERSION}/plantuml-${PLANTUML_VERSION}.jar" \
    && printf '%s\n' '#!/usr/bin/env sh' 'exec java -jar /opt/plantuml/plantuml.jar "$@"' | sudo tee /usr/local/bin/plantuml >/dev/null \
    && sudo chmod +x /usr/local/bin/plantuml
