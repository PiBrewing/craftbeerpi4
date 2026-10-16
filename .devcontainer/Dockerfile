FROM mcr.microsoft.com/vscode/devcontainers/python:3.14-trixie

RUN apt-get update && apt-get install --no-install-recommends -y \
    libsystemd-dev \
    libffi-dev \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*
RUN python3 -m pip install --no-cache-dir --upgrade pip setuptools wheel

# Install craftbeerpi requirements and additional-dev-requirements for better caching
COPY ./requirements.txt ./requirements-dev.txt ./.devcontainer/cbpi-default-dev-config/additional-dev-requirements.txt /workspace/
RUN pip3 install --no-cache-dir -r /workspace/requirements-dev.txt -r /workspace/additional-dev-requirements.txt

# Install current version of cbpi-ui (ADD refetches it when main changed)
ADD https://github.com/PiBrewing/craftbeerpi4-ui/archive/refs/heads/main.zip /opt/downloads/cbpi-ui.zip
RUN pip3 install --no-cache-dir /opt/downloads/cbpi-ui.zip \
    && rm -rf /opt/downloads