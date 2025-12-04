# LightRAG 多租户支持文档

## 📚 概述

LightRAG 通过 **workspace** 机制实现多租户数据隔离，确保不同租户的知识库数据完全独立。

## 🏗️ Workspace 架构

### 核心概念

- **Workspace**: 工作空间标识符，用于隔离不同租户的数据
- **默认 Workspace**: 如果不指定，使用服务器配置的默认 workspace
- **请求头传递**: 通过 HTTP 请求头 `LIGHTRAG-WORKSPACE` 传递工作空间信息

### 数据隔离方式

不同存储后端使用不同的隔离策略：

| 存储类型         | 隔离方式       | 存储后端                                                                                                                                                                     |
| ---------------- | -------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **文件系统**     | 子目录隔离     | `JsonKVStorage`, `JsonDocStatusStorage`, `NetworkXStorage`, `NanoVectorDBStorage`, `FaissVectorDBStorage`                                                                    |
| **集合/表前缀**  | 集合名加前缀   | `RedisKVStorage`, `RedisDocStatusStorage`, `MilvusVectorDBStorage`, `MongoKVStorage`, `MongoDocStatusStorage`, `MongoVectorDBStorage`, `MongoGraphStorage`, `PGGraphStorage` |
| **Payload 分区** | Payload 过滤   | `QdrantVectorDBStorage` (推荐的多租户方案)                                                                                                                                   |
| **字段隔离**     | workspace 字段 | `PGKVStorage`, `PGVectorStorage`, `PGDocStatusStorage`                                                                                                                       |
| **图数据库标签** | 节点标签隔离   | `Neo4JStorage`, `MemgraphStorage`                                                                                                                                            |

### 数据存储示例

#### 文件系统存储

```
rag_storage/
├── tenant_a/              # 租户A的workspace
│   ├── kv_store_entities.json
│   ├── kv_store_relations.json
│   └── graph.graphml
├── tenant_b/              # 租户B的workspace
│   ├── kv_store_entities.json
│   ├── kv_store_relations.json
│   └── graph.graphml
└── default/               # 默认workspace
    ├── kv_store_entities.json
    ├── kv_store_relations.json
    └── graph.graphml
```

#### PostgreSQL 存储

```sql
-- 使用 workspace 字段隔离
SELECT * FROM entities WHERE workspace = 'tenant_a';
SELECT * FROM entities WHERE workspace = 'tenant_b';

-- 或使用表前缀（图存储）
CREATE TABLE tenant_a.entities (...);
CREATE TABLE tenant_b.entities (...);
```

#### Neo4j 图存储

```cypher
-- 使用标签隔离
MATCH (n:tenant_a) RETURN n;
MATCH (n:tenant_b) RETURN n;
```

---

## 🔧 配置方式

### 方法 1: 环境变量（服务器默认）

在 `.env` 文件中配置默认 workspace：

```bash
# 默认 workspace
WORKSPACE=tenant_a

# 特定存储的 workspace（优先级更高）
REDIS_WORKSPACE=tenant_a
MILVUS_WORKSPACE=tenant_a
QDRANT_WORKSPACE=tenant_a
MONGODB_WORKSPACE=tenant_a
POSTGRES_WORKSPACE=tenant_a
NEO4J_WORKSPACE=tenant_a
MEMGRAPH_WORKSPACE=tenant_a
```

### 方法 2: 命令行参数

```bash
lightrag-server --workspace tenant_a

# 或
uvicorn lightrag.api.lightrag_server:app --reload
```

### 方法 3: HTTP 请求头（动态切换）

**推荐用于多租户应用**，每个请求可以指定不同的 workspace：

```bash
curl -H "LIGHTRAG-WORKSPACE: tenant_a" \
     http://localhost:8020/entities/list
```

---

## 🌐 API 使用方式

### 1. 实体和关系接口

所有新开发的实体、关系和 chunk 接口都支持 workspace：

```bash
# 租户A的实体列表
curl -H "LIGHTRAG-WORKSPACE: tenant_a" \
     "http://localhost:8020/entities/list?page=1&page_size=20"

# 租户B的实体列表
curl -H "LIGHTRAG-WORKSPACE: tenant_b" \
     "http://localhost:8020/entities/list?page=1&page_size=20"

# 使用默认workspace（不传header）
curl "http://localhost:8020/entities/list?page=1&page_size=20"
```

### 2. 查询接口

```bash
# 租户A的查询
curl -H "LIGHTRAG-WORKSPACE: tenant_a" \
     -H "Content-Type: application/json" \
     -d '{"query": "什么是特斯拉？", "mode": "local"}' \
     http://localhost:8020/query

# 租户B的查询
curl -H "LIGHTRAG-WORKSPACE: tenant_b" \
     -H "Content-Type: application/json" \
     -d '{"query": "什么是特斯拉？", "mode": "local"}' \
     http://localhost:8020/query
```

### 3. 文档管理接口

```bash
# 租户A上传文档
curl -H "LIGHTRAG-WORKSPACE: tenant_a" \
     -F "file=@document.txt" \
     http://localhost:8020/documents/upload

# 租户B上传文档
curl -H "LIGHTRAG-WORKSPACE: tenant_b" \
     -F "file=@document.txt" \
     http://localhost:8020/documents/upload
```

---

## 💻 客户端实现示例

### Python 客户端

```python
import requests

class LightRAGClient:
    def __init__(self, base_url: str, workspace: str, api_key: str = None):
        self.base_url = base_url
        self.workspace = workspace
        self.headers = {
            "LIGHTRAG-WORKSPACE": workspace
        }
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"

    def get_entities(self, page=1, page_size=20, entity_type=None):
        """获取实体列表"""
        params = {"page": page, "page_size": page_size}
        if entity_type:
            params["entity_type"] = entity_type

        response = requests.get(
            f"{self.base_url}/entities/list",
            params=params,
            headers=self.headers
        )
        return response.json()

    def query(self, query_text: str, mode: str = "local"):
        """查询知识库"""
        response = requests.post(
            f"{self.base_url}/query",
            json={"query": query_text, "mode": mode},
            headers=self.headers
        )
        return response.json()


# 使用示例
# 租户A的客户端
tenant_a_client = LightRAGClient(
    base_url="http://localhost:8020",
    workspace="tenant_a",
    api_key="your-api-key"
)

# 租户B的客户端
tenant_b_client = LightRAGClient(
    base_url="http://localhost:8020",
    workspace="tenant_b",
    api_key="your-api-key"
)

# 查询租户A的实体
tenant_a_entities = tenant_a_client.get_entities(entity_type="PERSON")
print(f"租户A有 {tenant_a_entities['total']} 个人物实体")

# 查询租户B的实体
tenant_b_entities = tenant_b_client.get_entities(entity_type="PERSON")
print(f"租户B有 {tenant_b_entities['total']} 个人物实体")
```

### JavaScript/TypeScript 客户端

```typescript
// lightrag-client.ts
import axios, { AxiosInstance } from "axios";

export class LightRAGClient {
  private client: AxiosInstance;

  constructor(baseURL: string, workspace: string, apiKey?: string) {
    this.client = axios.create({
      baseURL,
      headers: {
        "LIGHTRAG-WORKSPACE": workspace,
        ...(apiKey && { Authorization: `Bearer ${apiKey}` }),
      },
    });
  }

  async getEntities(params: {
    page?: number;
    page_size?: number;
    entity_type?: string;
    search?: string;
  }) {
    const response = await this.client.get("/entities/list", { params });
    return response.data;
  }

  async getEntityDetail(entityName: string) {
    const response = await this.client.get(
      `/entities/${encodeURIComponent(entityName)}`
    );
    return response.data;
  }

  async query(queryText: string, mode: string = "local") {
    const response = await this.client.post("/query", {
      query: queryText,
      mode,
    });
    return response.data;
  }
}

// 使用示例
const tenantAClient = new LightRAGClient(
  "http://localhost:8020",
  "tenant_a",
  "your-api-key"
);

const tenantBClient = new LightRAGClient(
  "http://localhost:8020",
  "tenant_b",
  "your-api-key"
);

// 查询租户A的实体
const tenantAEntities = await tenantAClient.getEntities({
  entity_type: "PERSON",
});
console.log(`租户A有 ${tenantAEntities.total} 个人物实体`);

// 查询租户B的实体
const tenantBEntities = await tenantBClient.getEntities({
  entity_type: "PERSON",
});
console.log(`租户B有 ${tenantBEntities.total} 个人物实体`);
```

### React 示例

```typescript
// TenantSelector.tsx - 租户选择组件
import React, { createContext, useContext, useState } from "react";
import { LightRAGClient } from "./lightrag-client";

interface TenantContextType {
  workspace: string;
  setWorkspace: (workspace: string) => void;
  client: LightRAGClient;
}

const TenantContext = createContext<TenantContextType | null>(null);

export function TenantProvider({ children }: { children: React.ReactNode }) {
  const [workspace, setWorkspace] = useState("default");
  const [client, setClient] = useState(
    () => new LightRAGClient("http://localhost:8020", workspace)
  );

  // 切换租户时更新客户端
  const handleSetWorkspace = (newWorkspace: string) => {
    setWorkspace(newWorkspace);
    setClient(new LightRAGClient("http://localhost:8020", newWorkspace));
  };

  return (
    <TenantContext.Provider
      value={{
        workspace,
        setWorkspace: handleSetWorkspace,
        client,
      }}
    >
      {children}
    </TenantContext.Provider>
  );
}

export function useTenant() {
  const context = useContext(TenantContext);
  if (!context) {
    throw new Error("useTenant must be used within TenantProvider");
  }
  return context;
}

// EntityList.tsx - 使用租户context的组件
export function EntityList() {
  const { client, workspace } = useTenant();
  const [entities, setEntities] = useState([]);

  useEffect(() => {
    async function loadEntities() {
      const data = await client.getEntities({ page: 1, page_size: 20 });
      setEntities(data.entities);
    }
    loadEntities();
  }, [client]);

  return (
    <div>
      <h2>当前租户: {workspace}</h2>
      <div>共 {entities.length} 个实体</div>
      {/* 实体列表渲染 */}
    </div>
  );
}
```

---

## 🔐 安全最佳实践

### 1. 租户身份验证

在生产环境中，应该将 workspace 与用户身份绑定：

```python
from fastapi import Request, HTTPException
from jose import jwt

def get_workspace_from_token(request: Request) -> str:
    """从 JWT token 中提取租户信息"""
    token = request.headers.get("Authorization", "").replace("Bearer ", "")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        workspace = payload.get("workspace")

        if not workspace:
            raise HTTPException(status_code=403, detail="No workspace in token")

        return workspace
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


# 在路由中使用
@router.get("/entities/list")
async def list_entities(
    request: Request,
    workspace: str = Depends(get_workspace_from_token)
):
    # 使用从 token 中提取的 workspace，而不是请求头
    # 这样可以防止用户伪造 workspace
    ...
```

### 2. Workspace 访问控制

```python
# 用户 <-> Workspace 映射
USER_WORKSPACES = {
    "user_alice": ["tenant_a"],
    "user_bob": ["tenant_b", "tenant_c"],  # 用户可以访问多个workspace
    "admin": ["*"],  # 管理员可以访问所有workspace
}

def check_workspace_access(username: str, workspace: str) -> bool:
    """检查用户是否有权访问指定workspace"""
    user_workspaces = USER_WORKSPACES.get(username, [])

    # 管理员有全部权限
    if "*" in user_workspaces:
        return True

    # 检查是否在用户的workspace列表中
    return workspace in user_workspaces


@router.get("/entities/list")
async def list_entities(
    request: Request,
    current_user: str = Depends(get_current_user)
):
    workspace = request.headers.get("LIGHTRAG-WORKSPACE", "default")

    # 验证访问权限
    if not check_workspace_access(current_user, workspace):
        raise HTTPException(
            status_code=403,
            detail=f"User {current_user} does not have access to workspace {workspace}"
        )

    # 继续处理...
```

### 3. 防止 Workspace 注入

```python
import re

def validate_workspace_name(workspace: str) -> str:
    """验证 workspace 名称，防止注入攻击"""
    # 只允许字母、数字、下划线和连字符
    if not re.match(r'^[a-zA-Z0-9_-]+$', workspace):
        raise HTTPException(
            status_code=400,
            detail="Invalid workspace name. Only alphanumeric, underscore and hyphen are allowed"
        )

    # 限制长度
    if len(workspace) > 50:
        raise HTTPException(
            status_code=400,
            detail="Workspace name too long (max 50 characters)"
        )

    return workspace
```

---

## 🧪 测试多租户隔离

### 测试脚本

```python
#!/usr/bin/env python3
"""测试多租户数据隔离"""

import requests

BASE_URL = "http://localhost:8020"

def test_workspace_isolation():
    """测试workspace数据隔离"""

    # 1. 在租户A中创建实体
    print("1. 在租户A中创建实体...")
    response = requests.post(
        f"{BASE_URL}/graph/entity/create",
        headers={"LIGHTRAG-WORKSPACE": "tenant_a"},
        json={
            "entity_name": "特斯拉A",
            "entity_data": {
                "description": "租户A的特斯拉",
                "entity_type": "ORGANIZATION"
            }
        }
    )
    assert response.status_code == 200
    print("✓ 租户A实体创建成功")

    # 2. 在租户B中创建实体
    print("\n2. 在租户B中创建实体...")
    response = requests.post(
        f"{BASE_URL}/graph/entity/create",
        headers={"LIGHTRAG-WORKSPACE": "tenant_b"},
        json={
            "entity_name": "特斯拉B",
            "entity_data": {
                "description": "租户B的特斯拉",
                "entity_type": "ORGANIZATION"
            }
        }
    )
    assert response.status_code == 200
    print("✓ 租户B实体创建成功")

    # 3. 验证租户A只能看到自己的实体
    print("\n3. 验证租户A的数据隔离...")
    response = requests.get(
        f"{BASE_URL}/entities/list",
        headers={"LIGHTRAG-WORKSPACE": "tenant_a"},
        params={"search": "特斯拉"}
    )
    data = response.json()
    entity_names = [e["entity_name"] for e in data["entities"]]

    assert "特斯拉A" in entity_names, "租户A应该能看到自己的实体"
    assert "特斯拉B" not in entity_names, "租户A不应该看到租户B的实体"
    print("✓ 租户A数据隔离正确")

    # 4. 验证租户B只能看到自己的实体
    print("\n4. 验证租户B的数据隔离...")
    response = requests.get(
        f"{BASE_URL}/entities/list",
        headers={"LIGHTRAG-WORKSPACE": "tenant_b"},
        params={"search": "特斯拉"}
    )
    data = response.json()
    entity_names = [e["entity_name"] for e in data["entities"]]

    assert "特斯拉B" in entity_names, "租户B应该能看到自己的实体"
    assert "特斯拉A" not in entity_names, "租户B不应该看到租户A的实体"
    print("✓ 租户B数据隔离正确")

    print("\n✅ 多租户数据隔离测试通过！")


if __name__ == "__main__":
    test_workspace_isolation()
```

---

## 📋 支持的接口列表

以下所有接口都支持通过 `LIGHTRAG-WORKSPACE` 请求头指定工作空间：

### 实体管理

- `GET /entities/list` - 获取实体列表
- `GET /entities/{entity_name}` - 获取实体详情
- `GET /entities/{entity_name}/relations` - 获取实体关系
- `POST /graph/entity/create` - 创建实体
- `POST /graph/entity/edit` - 编辑实体
- `POST /graph/entities/merge` - 合并实体

### 关系管理

- `GET /relations/list` - 获取关系列表
- `POST /graph/relation/create` - 创建关系
- `POST /graph/relation/edit` - 编辑关系

### 文档分块

- `GET /chunks/list` - 获取 chunks 列表
- `GET /chunks/{chunk_id}` - 获取 chunk 详情
- `GET /documents/{doc_id}/chunks` - 获取文档 chunks

### 查询

- `POST /query` - 知识库查询
- `POST /query/stream` - 流式查询
- `POST /query/data` - 数据查询

### 文档管理

- `POST /documents/upload` - 上传文档
- `GET /documents/list` - 文档列表
- `DELETE /documents/{doc_id}` - 删除文档

### 图谱管理

- `GET /graphs` - 获取知识图谱
- `GET /graph/label/list` - 获取标签列表
- `GET /graph/label/popular` - 获取热门标签

---

## 🔍 故障排查

### 问题 1: 数据没有隔离

**症状**: 租户 A 能看到租户 B 的数据

**解决方案**:

1. 检查是否正确传递 `LIGHTRAG-WORKSPACE` 请求头
2. 检查服务器日志，确认 workspace 被正确识别
3. 检查存储后端是否支持 workspace 隔离

### 问题 2: 切换 workspace 后看不到数据

**症状**: 切换到新的 workspace 后返回空数据

**原因**: 新的 workspace 还没有数据

**解决方案**: 这是正常的！新的 workspace 是空的，需要先上传文档或创建实体。

### 问题 3: 默认 workspace 行为不符合预期

**症状**: 不传 workspace 时的行为不符合预期

**解决方案**:

- 检查 `.env` 文件中的 `WORKSPACE` 配置
- 检查特定存储的 workspace 配置（如 `POSTGRES_WORKSPACE`）
- 对于 PostgreSQL，默认是 `default`
- 对于 Neo4j，默认是 `base`

---

## 🚀 生产环境建议

### 1. 使用数据库存储

对于生产环境，建议使用数据库存储（PostgreSQL、MongoDB、Neo4j 等）而不是 JSON 文件存储：

```bash
# .env 配置
KV_STORAGE=PGKVStorage
GRAPH_STORAGE=PGGraphStorage
VECTOR_STORAGE=PGVectorStorage
DOC_STATUS_STORAGE=PGDocStatusStorage

POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=lightrag
POSTGRES_PASSWORD=secure_password
POSTGRES_DATABASE=lightrag
```

### 2. 实施访问控制

- 将 workspace 与 JWT token 绑定
- 实施 RBAC (基于角色的访问控制)
- 记录所有跨租户访问尝试

### 3. 监控和审计

```python
import logging

audit_logger = logging.getLogger("audit")

def log_workspace_access(username: str, workspace: str, action: str):
    """记录workspace访问日志"""
    audit_logger.info(f"User {username} performed {action} on workspace {workspace}")
```

### 4. 性能优化

- 为 workspace 字段创建索引
- 使用连接池
- 考虑按 workspace 分片大型部署

---

## 📚 参考资料

- [LightRAG API 文档](./NewAPIEndpoints.md)
- [LightRAG 配置指南](./OfflineDeployment.md)
- [存储后端配置](../env.example)
