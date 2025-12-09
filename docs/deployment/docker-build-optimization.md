# Docker 构建优化指南

## 问题背景

在国内网络环境下，Docker 构建过程中的 `apt-get update` 和依赖安装非常缓慢，即使使用阿里云源也需要 5-10 分钟。

## 优化方案

### 方案 1: 使用清华源 + BuildKit 缓存（推荐）

**优点**: 无需预构建，首次慢但后续快
**适用**: 日常开发迭代

已在主 `Dockerfile` 中实现：

```dockerfile
# 使用清华源
RUN echo "deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm main contrib non-free non-free-firmware" > /etc/apt/sources.list

# 利用 BuildKit 缓存挂载
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && apt-get install -y --no-install-recommends curl build-essential pkg-config
```

**使用方法**:

```bash
# 确保启用 BuildKit（Docker 18.09+）
export DOCKER_BUILDKIT=1

# 构建（首次会慢，后续利用缓存会很快）
docker-compose build
```

### 方案 2: 预构建基础镜像（最快）

**优点**: 构建速度最快，跳过 apt-get 步骤
**适用**: CI/CD 环境或团队共享

#### 步骤 1: 创建预装依赖的基础镜像

```bash
# 启动临时容器
docker run --rm -it --name lightrag-preinstall \
  sobot-private-cloud.tencentcloudcr.com/base/python:3.12-slim bash

# 在容器内执行（手动或使用脚本）
# 方法A: 手动执行
cat > /etc/apt/sources.list << 'EOF'
deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm main contrib non-free non-free-firmware
deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm-updates main contrib non-free non-free-firmware
deb https://mirrors.tuna.tsinghua.edu.cn/debian-security bookworm-security main contrib non-free non-free-firmware
EOF

apt-get update
apt-get install -y --no-install-recommends curl build-essential pkg-config ca-certificates git
curl --proto '=https' --tlsv1.2 -sSf https://mirrors.tuna.tsinghua.edu.cn/rustup/rustup-init.sh | sh -s -- -y
rm -rf /var/lib/apt/lists/*
exit

# 方法B: 使用脚本（需要先复制到容器内）
# docker cp docker-preinstall-deps.sh lightrag-preinstall:/tmp/
# docker exec lightrag-preinstall bash /tmp/docker-preinstall-deps.sh
```

#### 步骤 2: 提交为新镜像

```bash
# 提交镜像
docker commit lightrag-preinstall \
  sobot-private-cloud.tencentcloudcr.com/base/python:3.12-slim-prebuilt

# 可选：推送到私有仓库供团队使用
docker push sobot-private-cloud.tencentcloudcr.com/base/python:3.12-slim-prebuilt
```

#### 步骤 3: 修改 Dockerfile 使用新镜像

方式 A: 直接修改 `Dockerfile` 第 6 行：

```dockerfile
FROM sobot-private-cloud.tencentcloudcr.com/base/python:3.12-slim-prebuilt AS builder
```

方式 B: 使用提供的 `Dockerfile.fast`：

```bash
docker-compose build --file docker-compose.yml --build-arg DOCKERFILE=Dockerfile.fast
# 或者修改 docker-compose.yml 中的 dockerfile 字段
```

### 方案 3: 本地宿主机预下载包（中等复杂度）

如果您有稳定的宿主机环境，可以预先下载 deb 包：

```bash
# 在宿主机上创建缓存目录
mkdir -p /tmp/apt-cache

# 使用容器下载包但不安装
docker run --rm -v /tmp/apt-cache:/cache \
  sobot-private-cloud.tencentcloudcr.com/base/python:3.12-slim bash -c "
  echo 'deb https://mirrors.tuna.tsinghua.edu.cn/debian/ bookworm main contrib non-free non-free-firmware' > /etc/apt/sources.list
  apt-get update
  apt-get install -y --download-only -o Dir::Cache::Archives=/cache \
    curl build-essential pkg-config
"

# 修改 Dockerfile 添加：
# COPY --from=cache /cache/*.deb /tmp/debs/
# RUN dpkg -i /tmp/debs/*.deb && rm -rf /tmp/debs
```

## 性能对比

| 方案                  | 首次构建 | 二次构建 | 复杂度 | 推荐场景    |
| --------------------- | -------- | -------- | ------ | ----------- |
| 默认（Debian 官方源） | ~10 分钟 | ~10 分钟 | 低     | ❌ 不推荐   |
| 清华源 + BuildKit     | ~3 分钟  | ~30 秒   | 低     | ✅ 日常开发 |
| 预构建基础镜像        | ~30 秒   | ~30 秒   | 中     | ✅ CI/CD    |
| 本地缓存包            | ~1 分钟  | ~1 分钟  | 高     | 特定场景    |

## 其他加速技巧

### 1. 启用 Docker BuildKit

```bash
# 临时启用
export DOCKER_BUILDKIT=1

# 永久启用（编辑 /etc/docker/daemon.json）
{
  "features": {
    "buildkit": true
  }
}
```

### 2. 使用国内 Docker 镜像加速器

```json
// /etc/docker/daemon.json
{
  "registry-mirrors": [
    "https://docker.mirrors.ustc.edu.cn",
    "https://hub-mirror.c.163.com"
  ]
}
```

### 3. 配置 pip 和 uv 使用清华源

```dockerfile
ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ENV UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
```

### 4. 并行下载（Rust/cargo）

```dockerfile
# 配置 Cargo 使用清华源
RUN mkdir -p /root/.cargo && \
    echo '[source.crates-io]' > /root/.cargo/config.toml && \
    echo 'replace-with = "tuna"' >> /root/.cargo/config.toml && \
    echo '[source.tuna]' >> /root/.cargo/config.toml && \
    echo 'registry = "https://mirrors.tuna.tsinghua.edu.cn/git/crates.io-index.git"' >> /root/.cargo/config.toml
```

## 故障排查

### 问题 1: 清华源连接超时

```bash
# 尝试其他镜像源
# 科大源
deb https://mirrors.ustc.edu.cn/debian/ bookworm main contrib non-free non-free-firmware

# 阿里云源
deb http://mirrors.aliyun.com/debian/ bookworm main non-free non-free-firmware

# 华为云源
deb https://mirrors.huaweicloud.com/debian/ bookworm main contrib non-free non-free-firmware
```

### 问题 2: BuildKit 缓存未生效

```bash
# 清理缓存重新构建
docker builder prune -af
docker-compose build --no-cache
```

### 问题 3: 预构建镜像找不到

```bash
# 检查镜像是否存在
docker images | grep prebuilt

# 如果不存在，重新执行方案2的步骤1-2
```

## 总结

- **开发环境**: 使用方案 1（清华源 + BuildKit），已在主 Dockerfile 实现
- **生产/CI**: 使用方案 2（预构建镜像），一次性投入，长期受益
- **临时解决**: Ctrl+C 取消构建，使用 `docker-compose build --no-cache` 清理后重试

当前 `Dockerfile` 已更新为方案 1，可以直接使用：

```bash
export DOCKER_BUILDKIT=1
docker-compose build
```
