# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim AS frontend
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM debian:bookworm-slim AS speech
ARG TARGETARCH
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl git cmake g++ make && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 --branch v1.9.2 https://github.com/ggml-org/whisper.cpp.git /src/whisper \
    && cmake -S /src/whisper -B /src/whisper/build -DGGML_NATIVE=OFF -DGGML_METAL=OFF -DGGML_CUDA=OFF -DWHISPER_BUILD_TESTS=OFF -DCMAKE_INSTALL_PREFIX=/opt/whisper -DCMAKE_INSTALL_RPATH=/opt/whisper/lib \
    && cmake --build /src/whisper/build --config Release -j 4 \
    && cmake --install /src/whisper/build
RUN case "$TARGETARCH" in \
      arm64) arch=aarch64; digest=0e4112255d566de7bdd142f239e984995c4447103ba8feb41f2bb5c559d561d3 ;; \
      amd64) arch=x86_64; digest=0f74131d631ad2c694cf0ec53490866bb6461147959589a69fb6fc231944065b ;; \
      *) exit 1 ;; \
    esac \
    && curl -fsSL "https://github.com/NVIDIA/NeMo-Speech.cpp/releases/download/v0.1.0/nemo-speech-0.1.0-linux-${arch}-cpu.tar.gz" -o /tmp/nemo.tar.gz \
    && echo "$digest  /tmp/nemo.tar.gz" | sha256sum -c - \
    && mkdir /opt/nemo-speech \
    && tar -xzf /tmp/nemo.tar.gz -C /opt/nemo-speech --strip-components=1

FROM python:3.11-slim-bookworm AS app
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libgomp1 ca-certificates socat && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY --from=speech /opt/whisper /opt/whisper
COPY --from=speech /opt/nemo-speech /opt/nemo-speech
ENV PATH="/opt/whisper/bin:/opt/nemo-speech/bin:$PATH" \
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1 \
    PYTHONUNBUFFERED=1
COPY backend/ backend/
COPY scripts/ scripts/
COPY demo/ demo/
COPY pyproject.toml ./
RUN pip install --no-cache-dir --no-deps .
COPY --from=frontend /build/dist frontend/dist/
EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
