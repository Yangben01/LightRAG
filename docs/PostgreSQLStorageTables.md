# PostgreSQL 存储表说明

## 存储配置与数据库表的对应关系

### 1. `LIGHTRAG_GRAPH_STORAGE=PGGraphStorage`

**使用的存储方式**：PostgreSQL + Apache AGE 扩展（图数据库）

**不是普通表**，而是使用 AGE 创建的图结构：

- **图名称格式**：`{workspace}_{namespace}` 或 `{namespace}`（如果 workspace 是 default）
- **实际存储位置**：
  - 节点表：`{graph_name}."base"` - 存储实体节点
  - 边表：`{graph_name}."DIRECTED"` - 存储关系边
  - 元数据表：`{graph_name}."_ag_label_vertex"` 和 `{graph_name}."_ag_label_edge"`

**示例**（workspace=space1）：
```sql
-- 查看所有 AGE 图
SELECT * FROM ag_catalog.ag_graph;

-- 查看节点（实体）
SELECT * FROM space1_chunk_entity_relation."base";

-- 查看边（关系）
SELECT * FROM space1_chunk_entity_relation."DIRECTED";
```

**特点**：
- 需要安装 PostgreSQL AGE 扩展
- 使用 Cypher 查询语言
- 适合复杂的图查询和遍历

---

### 2. `LIGHTRAG_VECTOR_STORAGE=PGVectorStorage`

**使用的数据库表**：

#### 表1: `LIGHTRAG_VDB_CHUNKS`
存储文档分块的向量数据

```sql
CREATE TABLE LIGHTRAG_VDB_CHUNKS (
    id VARCHAR(255),
    workspace VARCHAR(255),
    full_doc_id VARCHAR(256),
    chunk_order_index INTEGER,
    tokens INTEGER,
    content TEXT,
    content_vector VECTOR(1024),  -- 向量数据
    file_path TEXT NULL,
    create_time TIMESTAMP(0) DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP(0) DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT LIGHTRAG_VDB_CHUNKS_PK PRIMARY KEY (workspace, id)
)
```

#### 表2: `LIGHTRAG_VDB_ENTITY`
存储实体的向量数据

```sql
CREATE TABLE LIGHTRAG_VDB_ENTITY (
    id VARCHAR(255),
    workspace VARCHAR(255),
    entity_name VARCHAR(512),
    content TEXT,
    content_vector VECTOR(1024),  -- 向量数据
    create_time TIMESTAMP(0) DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP(0) DEFAULT CURRENT_TIMESTAMP,
    chunk_ids VARCHAR(255)[] NULL,
    file_path TEXT NULL,
    CONSTRAINT LIGHTRAG_VDB_ENTITY_PK PRIMARY KEY (workspace, id)
)
```

#### 表3: `LIGHTRAG_VDB_RELATION`
存储关系的向量数据

```sql
CREATE TABLE LIGHTRAG_VDB_RELATION (
    id VARCHAR(255),
    workspace VARCHAR(255),
    source_id VARCHAR(512),
    target_id VARCHAR(512),
    content TEXT,
    content_vector VECTOR(1024),  -- 向量数据
    create_time TIMESTAMP(0) DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP(0) DEFAULT CURRENT_TIMESTAMP,
    chunk_ids VARCHAR(255)[] NULL,
    file_path TEXT NULL,
    CONSTRAINT LIGHTRAG_VDB_RELATION_PK PRIMARY KEY (workspace, id)
)
```

**特点**：
- 需要安装 `pgvector` 扩展
- 支持向量相似度搜索
- 使用 HNSW 或 IVFFlat 索引优化查询

---

## 当前配置状态

根据你的 `dev.env` 文件：

```bash
LIGHTRAG_KV_STORAGE=PGKVStorage              # ✅ 已配置
# LIGHTRAG_DOC_STATUS_STORAGE=PGDocStatusStorage  # ❌ 未配置（使用JSON）
LIGHTRAG_GRAPH_STORAGE=Neo4JStorage          # ✅ 使用 Neo4J（不是 PostgreSQL）
# LIGHTRAG_GRAPH_STORAGE=PGGraphStorage      # ❌ 被注释
# LIGHTRAG_VECTOR_STORAGE=PGVectorStorage     # ❌ 被注释
```

### 当前实际使用的存储：

| 存储类型 | 配置值 | 实际存储位置 |
|---------|--------|------------|
| KV_STORAGE | `PGKVStorage` | PostgreSQL 表 |
| DOC_STATUS_STORAGE | `JsonDocStatusStorage` (默认) | JSON 文件 |
| GRAPH_STORAGE | `Neo4JStorage` | Neo4j 数据库 |
| VECTOR_STORAGE | `NanoVectorDBStorage` (默认) | 本地文件 |

---

## 如果要全部使用 PostgreSQL

修改 `dev.env`：

```bash
# KV 存储
LIGHTRAG_KV_STORAGE=PGKVStorage

# 文档状态存储
LIGHTRAG_DOC_STATUS_STORAGE=PGDocStatusStorage  # 取消注释

# 图存储（二选一）
LIGHTRAG_GRAPH_STORAGE=PGGraphStorage          # 使用 PostgreSQL AGE
# 或
# LIGHTRAG_GRAPH_STORAGE=Neo4JStorage           # 使用 Neo4j（当前配置）

# 向量存储
LIGHTRAG_VECTOR_STORAGE=PGVectorStorage        # 取消注释
```

---

## 数据库表总览

如果全部使用 PostgreSQL，会使用以下表：

| 表名 | 用途 | 存储类型 |
|------|------|---------|
| `LIGHTRAG_DOC_FULL` | 文档完整内容 | KV |
| `LIGHTRAG_DOC_CHUNKS` | 文档分块 | KV |
| `LIGHTRAG_DOC_STATUS` | 文档处理状态 | DOC_STATUS |
| `LIGHTRAG_VDB_CHUNKS` | 分块向量 | VECTOR |
| `LIGHTRAG_VDB_ENTITY` | 实体向量 | VECTOR |
| `LIGHTRAG_VDB_RELATION` | 关系向量 | VECTOR |
| `LIGHTRAG_FULL_ENTITIES` | 实体完整信息 | KV |
| `LIGHTRAG_FULL_RELATIONS` | 关系完整信息 | KV |
| `LIGHTRAG_LLM_CACHE` | LLM 响应缓存 | KV |
| `LIGHTRAG_CATEGORIES` | 分类信息 | 新增 |
| `{graph_name}."base"` | 图节点（AGE） | GRAPH |
| `{graph_name}."DIRECTED"` | 图边（AGE） | GRAPH |

---

## 注意事项

1. **PGGraphStorage 需要 AGE 扩展**：
   - 需要安装 PostgreSQL AGE 扩展
   - 如果未安装，图存储会失败

2. **PGVectorStorage 需要 pgvector 扩展**：
   - 需要安装 `pgvector` 扩展
   - 支持向量相似度搜索

3. **Neo4J vs PGGraphStorage**：
   - Neo4J：专业的图数据库，性能更好
   - PGGraphStorage：基于 PostgreSQL + AGE，一体化方案

4. **数据迁移**：
   - 从 JSON/Neo4J 切换到 PostgreSQL 需要数据迁移
   - 建议先备份数据

