FROM mcr.microsoft.com/devcontainers/java:3.1.3-17-bookworm

ARG PLANTUML_VERSION=1.2026.5

RUN sudo apt-get update \
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
