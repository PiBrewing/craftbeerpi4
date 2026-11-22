# Pinned by digest so the image (and the build cache) only changes with an
# explicit bump. Dependabot proposes the 3.14.x patch releases.
FROM python:3.14.8-trixie@sha256:446efb4225200a0a196707aa7953898b37962fd3b8859a636035de3af657081e AS base

# Install dependencies
RUN apt-get update && apt-get install --no-install-recommends -y \
    libsystemd-dev \
    libffi-dev \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

ENV VIRTUAL_ENV=/opt/venv

# Create non-root user working directory
RUN groupadd -g 1000 -r craftbeerpi \
    && useradd -u 1000 -r -s /bin/false -g craftbeerpi craftbeerpi \
    && mkdir /cbpi \
    && chown craftbeerpi:craftbeerpi /cbpi \
    && mkdir -p $VIRTUAL_ENV \
    && chown -R craftbeerpi:craftbeerpi ${VIRTUAL_ENV}

USER craftbeerpi

# create virtual environment
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

RUN python3 -m pip install --no-cache-dir --upgrade pip setuptools wheel

# Install craftbeerpi requirements for better caching
COPY --chown=craftbeerpi ./requirements.txt /cbpi-src/
RUN pip3 install --no-cache-dir -r /cbpi-src/requirements.txt

# Install RPi.GPIO separately because it's excluded in setup.py for non-raspberrys.
# This can enable GPIO support for the image when used on a raspberry pi and the
# /dev/gpiomem device.
RUN pip3 install --no-cache-dir RPi.GPIO==0.7.1

# Test dependencies, for the CI and .github/ci-local.sh. Not in the image.
FROM base AS test
COPY --chown=craftbeerpi ./requirements-dev.txt /cbpi-src/
RUN pip3 install --no-cache-dir -r /cbpi-src/requirements-dev.txt

FROM base AS deploy
# Install craftbeerpi-ui first: it provides the cbpi4gui requirement of
# setup.py (not fetched from PyPI), and a source change does not reinstall
# it. ADD fetches the archive on every build and only invalidates the cache
# when its content changed, so a new UI commit always reaches the image (a
# RUN curl layer stayed cached on the old UI forever).
ARG CBPI_UI_REF=main
ADD --chown=craftbeerpi https://github.com/PiBrewing/craftbeerpi4-ui/archive/refs/heads/${CBPI_UI_REF}.zip /downloads/cbpi-ui.zip
RUN pip3 install --no-cache-dir /downloads/cbpi-ui.zip

# Install craftbeerpi from source
COPY --chown=craftbeerpi . /cbpi-src
RUN pip3 install --no-cache-dir /cbpi-src

# Clean up installation files
USER root
RUN rm -rf /downloads /cbpi-src
USER craftbeerpi

WORKDIR /cbpi
RUN ["cbpi", "setup"]

EXPOSE 8000

# Start cbpi
CMD ["cbpi", "start"]
