# syntax=docker/dockerfile:1

# ==========================
# Python build stage - using uv for faster package installation
# ==========================
FROM sobot-private-cloud.tencentcloudcr.com/base/python:3.12-slim AS builder

ENV DEBIAN_FRONTEND=noninteractive \
    UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1

WORKDIR /app

# ✅ 配置 apt 加速选项（和 backend 一致）
RUN echo 'Acquire::http::Pipeline-Depth "5";' > /etc/apt/apt.conf.d/99parallel && \
    echo 'Acquire::http::No-Cache "true";' >> /etc/apt/apt.conf.d/99parallel && \
    echo 'Acquire::BrokenProxy "true";' >> /etc/apt/apt.conf.d/99parallel && \
    echo 'Acquire::http::Timeout "30";' >> /etc/apt/apt.conf.d/99parallel && \
    echo 'Acquire::ftp::Timeout "30";' >> /etc/apt/apt.conf.d/99parallel && \
    echo 'APT::Get::Assume-Yes "true";' >> /etc/apt/apt.conf.d/99parallel && \
    echo 'APT::Install-Recommends "false";' >> /etc/apt/apt.conf.d/99parallel

# ✅ 使用阿里云 Trixie 源（彻底替换，避免回退到官方源）
RUN rm -f /etc/apt/sources.list.d/* && \
    echo "# 阿里云 Debian Trixie 镜像源" > /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian/ trixie main contrib non-free non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian/ trixie-updates main contrib non-free non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian/ trixie-backports main contrib non-free non-free-firmware" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian-security/ trixie-security main contrib non-free non-free-firmware" >> /etc/apt/sources.list

# ✅ 安装构建依赖并配置 Rust 国内源
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update -o Acquire::Check-Valid-Until=false -o Acquire::Retries=3 && \
    apt-get install -y --no-install-recommends \
        curl \
        build-essential \
        pkg-config \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* /var/cache/apt/archives/*

# ✅ 配置 Rust 使用中科大源（比清华更稳定）
ENV RUSTUP_DIST_SERVER=https://mirrors.ustc.edu.cn/rust-static \
    RUSTUP_UPDATE_ROOT=https://mirrors.ustc.edu.cn/rust-static/rustup

RUN curl --proto '=https' --tlsv1.2 -sSf https://rsproxy.cn/rustup-init.sh | sh -s -- -y --default-toolchain stable --no-modify-path

ENV PATH="/root/.cargo/bin:/root/.local/bin:${PATH}"

# ✅ 配置 Cargo 使用国内镜像（中科大源）
RUN mkdir -p /root/.cargo && \
    echo '[source.crates-io]' > /root/.cargo/config.toml && \
    echo 'replace-with = "ustc"' >> /root/.cargo/config.toml && \
    echo '' >> /root/.cargo/config.toml && \
    echo '[source.ustc]' >> /root/.cargo/config.toml && \
    echo 'registry = "sparse+https://mirrors.ustc.edu.cn/crates.io-index/"' >> /root/.cargo/config.toml && \
    echo '' >> /root/.cargo/config.toml && \
    echo '[net]' >> /root/.cargo/config.toml && \
    echo 'git-fetch-with-cli = true' >> /root/.cargo/config.toml

# ✅ 配置 uv 使用清华 PyPI 源
RUN mkdir -p /root/.local/share/uv && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    /root/.local/bin/uv pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple/ && \
    /root/.local/bin/uv pip config set install.trusted-host pypi.tuna.tsinghua.edu.cn

# Install Python dependencies
COPY pyproject.toml setup.py uv.lock ./
RUN --mount=type=cache,target=/root/.local/share/uv \
    --mount=type=cache,target=/root/.cargo/registry \
    --mount=type=cache,target=/root/.cargo/git \
    uv sync --frozen --no-dev --extra api --extra offline --no-install-project --no-editable

COPY lightrag/ ./lightrag/
RUN --mount=type=cache,target=/root/.local/share/uv \
    --mount=type=cache,target=/root/.cargo/registry \
    --mount=type=cache,target=/root/.cargo/git \
    uv sync --frozen --no-dev --extra api --extra offline --no-editable \
    && /app/.venv/bin/python -m ensurepip --upgrade

# Download tiktoken cache
RUN mkdir -p /app/data/tiktoken \
    && uv run lightrag-download-cache --cache-dir /app/data/tiktoken || status=$?; \
    if [ -n "${status:-}" ] && [ "$status" -ne 0 ] && [ "$status" -ne 2 ]; then exit "$status"; fi


# ==========================
# Final Stage
# ==========================
FROM sobot-private-cloud.tencentcloudcr.com/base/python:3.12-slim

WORKDIR /app

ENV UV_SYSTEM_PYTHON=1

# ✅ 从 builder 阶段复制必要文件
COPY --from=builder /root/.local/bin/uv /usr/local/bin/uv
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/lightrag ./lightrag
COPY --from=builder /app/data/tiktoken /app/data/tiktoken
COPY pyproject.toml setup.py uv.lock ./

ENV PATH=/app/.venv/bin:$PATH \
    TIKTOKEN_CACHE_DIR=/app/data/tiktoken \
    WORKING_DIR=/app/data/rag_storage \
    INPUT_DIR=/app/data/inputs

RUN mkdir -p /app/data/rag_storage /app/data/inputs

EXPOSE 9621
ENTRYPOINT ["python", "-m", "lightrag.api.lightrag_server"]
