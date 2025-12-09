# Docker 运行时依赖安装指南

## 问题：docker exec 安装后是否需要重启服务？

### 答案：**需要重启服务**

### 原因分析

1. **Python 模块导入机制**
   - LightRAG 的存储后端（Redis、Neo4j 等）在模块**首次导入时**检查并安装依赖
   - 查看代码：`lightrag/kg/redis_impl.py` 和 `lightrag/kg/neo4j_impl.py` 在模块级别检查依赖
   ```python
   if not pm.is_installed("redis"):
       pm.install("redis")
   from redis.asyncio import Redis  # 这行在模块导入时执行
   ```

2. **运行时安装的限制**
   - 如果服务已经启动，即使通过 `docker exec` 安装了新包，**已运行的 Python 进程不会自动重新导入模块**
   - Python 的 `import` 是静态的，已导入的模块会缓存在 `sys.modules` 中
   - 新安装的包只有在**下次启动时**才会被检测和使用

### 重启方式

#### 方法 1：重启容器（推荐）
```bash
docker restart lightrag
```

#### 方法 2：使用 docker-compose
```bash
docker compose restart lightrag
```

#### 方法 3：停止并启动
```bash
docker stop lightrag
docker start lightrag
```

### 重启后的影响

✅ **不会影响数据和配置**，原因：

1. **数据持久化**
   - 数据存储在挂载的 volume：`./data/rag_storage:/app/data/rag_storage`
   - 重启不会删除 volume 中的数据

2. **配置持久化**
   - `.env` 文件挂载：`./.env:/app/.env`
   - `config.ini` 文件挂载：`./config.ini:/app/config.ini`
   - 配置在容器外部，重启不影响

3. **服务状态**
   - 容器配置了 `restart: unless-stopped`，会自动重启
   - 服务启动命令：`python -m lightrag.api.lightrag_server`
   - 重启后会自动重新加载配置和连接存储后端

### 依赖安装策略

#### 阶段 1：快速启动（当前）
```dockerfile
# Dockerfile 中只安装 api 依赖
--extra api
```
- ✅ 构建快，能启动
- ✅ 覆盖 80% 使用场景（默认存储、OpenAI 等）
- ❌ 无法使用 Redis、Neo4j、Milvus 等

#### 阶段 2：运行时安装（按需扩展）
```bash
# 在运行中的容器内安装额外依赖（必须使用虚拟环境中的 Python）
docker exec lightrag /app/.venv/bin/python -m pip install redis neo4j

# 然后重启服务使依赖生效
docker restart lightrag
```

**注意**：必须使用 `/app/.venv/bin/python -m pip install` 而不是 `pip install`，确保安装到正确的虚拟环境。

#### 阶段 3：完整部署（确认需要后）
```dockerfile
# Dockerfile 中安装完整依赖
--extra api --extra offline
```
- ✅ 包含所有存储后端和 LLM 提供商
- ⚠️ 构建时间较长，镜像体积较大

### 验证安装是否生效

重启后，可以通过以下方式验证：

1. **检查日志**
   ```bash
   docker logs lightrag
   ```
   查看是否有依赖相关的错误信息

2. **测试连接**
   - 如果配置了 Redis/Neo4j，检查服务日志中是否有连接成功的消息
   - 或者通过 API 测试相关功能

3. **检查 Python 环境**（使用虚拟环境中的 Python）
   ```bash
   docker exec lightrag /app/.venv/bin/python -c "import redis; print('Redis installed')"
   docker exec lightrag /app/.venv/bin/python -c "import neo4j; print('Neo4j installed')"
   docker exec lightrag /app/.venv/bin/python -c "from bs4 import BeautifulSoup; print('beautifulsoup4 installed')"
   ```

### 最佳实践建议

1. **开发环境**：使用阶段 2（运行时安装），灵活快速
2. **生产环境**：使用阶段 3（完整安装），避免运行时依赖问题
3. **CI/CD**：根据实际使用的存储后端，选择最小化依赖集

### 常见问题：beautifulsoup4 未安装

如果遇到错误：`beautifulsoup4未安装，无法解析网页`

**原因**：
- `beautifulsoup4` 虽然在 `api` 依赖中定义，但可能因为构建问题未正确安装
- 代码在运行时检查导入，如果失败会抛出异常（与存储后端不同，这里没有自动安装）

**解决方案**：

1. **立即解决**（推荐）：
   ```bash
   # 重要：必须使用虚拟环境中的 Python 来安装，否则会安装到系统 Python
   # 容器使用虚拟环境 /app/.venv，服务启动时使用的是虚拟环境中的 Python
   docker exec lightrag /app/.venv/bin/python -m pip install beautifulsoup4
   
   # 重启服务使依赖生效
   docker restart lightrag
   ```

2. **验证安装**：
   ```bash
   # 使用虚拟环境中的 Python 验证
   docker exec lightrag /app/.venv/bin/python -c "from bs4 import BeautifulSoup; print('beautifulsoup4 安装成功')"
   ```

3. **替代方法**（如果虚拟环境中有 uv）：
   ```bash
   docker exec lightrag uv pip install beautifulsoup4
   ```

**重要提示**：
- ❌ **不要使用** `docker exec lightrag pip install`，这会安装到系统 Python（`/usr/local/lib/python3.12/site-packages`）
- ✅ **必须使用** `/app/.venv/bin/python -m pip install`，这会安装到虚拟环境（`/app/.venv/lib/python3.12/site-packages`）
- 容器启动命令使用的是虚拟环境中的 Python，所以依赖必须安装在虚拟环境中

3. **长期解决**：
   - 重新构建 Docker 镜像，确保 `api` 依赖正确安装
   - 或者将 `beautifulsoup4` 添加到 Dockerfile 的显式安装列表中

**注意**：`httpx` 也可能遇到同样的问题，使用相同的解决方案。

### 相关文件

- Dockerfile：`/Dockerfile`
- docker-compose.yml：`/docker-compose.yml`
- 依赖定义：`/pyproject.toml`
- 存储后端实现：`/lightrag/kg/`
- 文档路由：`/lightrag/api/routers/document_routes.py`

