FROM mcr.microsoft.com/devcontainers/java:3.1.3-17-bookworm

ARG PLANTUML_VERSION=1.2025.10

RUN sudo apt-get update \
    && sudo apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        fonts-dejavu \
        graphviz \
        make \
        maven \
        python3 \
    && sudo rm -rf /var/lib/apt/lists/*

RUN sudo mkdir -p /opt/plantuml \
    && sudo curl -fsSL -o /opt/plantuml/plantuml.jar "https://github.com/plantuml/plantuml/releases/download/v${PLANTUML_VERSION}/plantuml-${PLANTUML_VERSION}.jar" \
    && printf '%s\n' '#!/usr/bin/env sh' 'exec java -jar /opt/plantuml/plantuml.jar "$@"' | sudo tee /usr/local/bin/plantuml >/dev/null \
    && sudo chmod +x /usr/local/bin/plantuml

ENV PLANTUML_LIMIT_SIZE=4096
