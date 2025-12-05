# PostgreSQL 向量存储配置指南

## 配置步骤

### 1. 修改存储配置

在 `dev.env` 文件中，取消注释向量存储配置：

```bash
# 修改前
# LIGHTRAG_VECTOR_STORAGE=PGVectorStorage

# 修改后
LIGHTRAG_VECTOR_STORAGE=PGVectorStorage
```

### 2. 确保 PostgreSQL 连接配置正确

```bash
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD='postgres'
POSTGRES_DATABASE=geo_saas
```

### 3. 配置向量索引类型（可选，已有默认值）

```bash
# 向量索引类型: HNSW, IVFFlat, VCHORDRQ
POSTGRES_VECTOR_INDEX_TYPE=HNSW

# HNSW 索引参数
POSTGRES_HNSW_M=16
POSTGRES_HNSW_EF=200

# IVFFlat 索引参数
POSTGRES_IVFFLAT_LISTS=100

# VCHORDRQ 索引参数（如果使用）
POSTGRES_VCHORDRQ_BUILD_OPTIONS=
POSTGRES_VCHORDRQ_PROBES=
POSTGRES_VCHORDRQ_EPSILON=1.9
```

### 4. 配置向量相似度阈值（可选，默认 0.2）

```bash
# 向量相似度阈值（余弦相似度）
# 值越小，匹配越严格；值越大，匹配越宽松
COSINE_THRESHOLD=0.2
```

### 5. 确保 Embedding 维度配置正确

```bash
# 必须与你的 embedding 模型维度一致
EMBEDDING_DIM=1024
```

## 自动安装 pgvector 扩展

**好消息**：LightRAG 会自动创建 `pgvector` 扩展！

启动服务器时，系统会自动执行：
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

**前提条件**：
- PostgreSQL 必须已安装 `pgvector` 扩展
- 如果未安装，需要手动安装

### 手动安装 pgvector（如果需要）

#### 方法1：使用 apt（Ubuntu/Debian）
```bash
sudo apt-get install postgresql-14-pgvector  # 根据你的 PostgreSQL 版本调整
```

#### 方法2：从源码编译
```bash
git clone --branch v0.5.1 https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install
```

#### 方法3：使用 Docker
```bash
docker run -d \
  --name postgres-pgvector \
  -e POSTGRES_PASSWORD=postgres \
  -p 5432:5432 \
  pgvector/pgvector:pg16
```

#### 安装后验证
```sql
-- 连接到 PostgreSQL
psql -U postgres -d geo_saas

-- 检查扩展是否可用
SELECT * FROM pg_available_extensions WHERE name = 'vector';

-- 如果已安装，应该能看到
```

## 数据库表结构

启用 PGVectorStorage 后，会自动创建以下表：

### 1. LIGHTRAG_VDB_CHUNKS
存储文档分块的向量数据

```sql
CREATE TABLE LIGHTRAG_VDB_CHUNKS (
    id VARCHAR(255),
    workspace VARCHAR(255),
    full_doc_id VARCHAR(256),
    chunk_order_index INTEGER,
    tokens INTEGER,
    content TEXT,
    content_vector VECTOR(1024),  -- 向量维度由 EMBEDDING_DIM 决定
    file_path TEXT NULL,
    create_time TIMESTAMP(0) DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP(0) DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT LIGHTRAG_VDB_CHUNKS_PK PRIMARY KEY (workspace, id)
);
```

### 2. LIGHTRAG_VDB_ENTITY
存储实体的向量数据

```sql
CREATE TABLE LIGHTRAG_VDB_ENTITY (
    id VARCHAR(255),
    workspace VARCHAR(255),
    entity_name VARCHAR(512),
    content TEXT,
    content_vector VECTOR(1024),
    create_time TIMESTAMP(0) DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP(0) DEFAULT CURRENT_TIMESTAMP,
    chunk_ids VARCHAR(255)[] NULL,
    file_path TEXT NULL,
    CONSTRAINT LIGHTRAG_VDB_ENTITY_PK PRIMARY KEY (workspace, id)
);
```

### 3. LIGHTRAG_VDB_RELATION
存储关系的向量数据

```sql
CREATE TABLE LIGHTRAG_VDB_RELATION (
    id VARCHAR(255),
    workspace VARCHAR(255),
    source_id VARCHAR(512),
    target_id VARCHAR(512),
    content TEXT,
    content_vector VECTOR(1024),
    create_time TIMESTAMP(0) DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP(0) DEFAULT CURRENT_TIMESTAMP,
    chunk_ids VARCHAR(255)[] NULL,
    file_path TEXT NULL,
    CONSTRAINT LIGHTRAG_VDB_RELATION_PK PRIMARY KEY (workspace, id)
);
```

## 向量索引

系统会自动创建向量索引以优化查询性能：

### HNSW 索引（推荐）
```sql
CREATE INDEX idx_lightrag_vdb_chunks_hnsw_cosine 
ON LIGHTRAG_VDB_CHUNKS 
USING hnsw (content_vector vector_cosine_ops);
```

### IVFFlat 索引
```sql
CREATE INDEX idx_lightrag_vdb_chunks_ivfflat_cosine 
ON LIGHTRAG_VDB_CHUNKS 
USING ivfflat (content_vector vector_cosine_ops) 
WITH (lists = 100);
```

## 验证配置

### 1. 检查扩展是否安装
```sql
SELECT * FROM pg_extension WHERE extname = 'vector';
```

### 2. 检查表是否创建
```sql
SELECT table_name 
FROM information_schema.tables 
WHERE table_name LIKE 'LIGHTRAG_VDB%';
```

### 3. 检查索引是否创建
```sql
SELECT indexname, tablename 
FROM pg_indexes 
WHERE tablename LIKE 'LIGHTRAG_VDB%' 
AND indexname LIKE '%vector%';
```

### 4. 测试向量查询
```sql
-- 查询相似的向量（示例）
SELECT id, content, 
       content_vector <=> '[0.1,0.2,...]'::vector AS distance
FROM LIGHTRAG_VDB_CHUNKS
WHERE workspace = 'space1'
ORDER BY distance
LIMIT 10;
```

## 常见问题

### Q1: 启动时报错 "Could not create VECTOR extension"
**原因**：PostgreSQL 未安装 pgvector 扩展

**解决**：
1. 安装 pgvector 扩展（见上方安装步骤）
2. 重启 PostgreSQL 服务
3. 重新启动 LightRAG 服务器

### Q2: 向量维度不匹配
**原因**：`EMBEDDING_DIM` 配置与 embedding 模型实际维度不一致

**解决**：
1. 检查你的 embedding 模型维度
2. 确保 `EMBEDDING_DIM` 配置正确
3. 如果已创建表，需要删除重建或迁移数据

### Q3: 查询性能慢
**原因**：未创建向量索引或索引类型不合适

**解决**：
1. 检查索引是否创建：`SELECT * FROM pg_indexes WHERE tablename LIKE 'LIGHTRAG_VDB%';`
2. 对于大数据量，推荐使用 HNSW 索引
3. 调整 HNSW 参数（M, ef）以平衡性能和精度

### Q4: 如何从其他向量存储迁移到 PostgreSQL？
**解决**：
1. 先配置好 PostgreSQL 向量存储
2. 重新索引文档（上传或重新处理）
3. 系统会自动将向量数据写入 PostgreSQL

## 性能优化建议

1. **使用 HNSW 索引**：适合大多数场景，查询速度快
2. **调整 HNSW 参数**：
   - `M=16`：平衡内存和性能（默认）
   - `ef=200`：查询时的候选数量（默认）
3. **连接池配置**：确保 `POSTGRES_MAX_CONNECTIONS` 足够
4. **定期 VACUUM**：清理数据库以保持性能

## 完整配置示例

```bash
# 存储配置
LIGHTRAG_VECTOR_STORAGE=PGVectorStorage

# PostgreSQL 连接
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_USER=postgres
POSTGRES_PASSWORD='postgres'
POSTGRES_DATABASE=geo_saas
POSTGRES_MAX_CONNECTIONS=12

# 向量索引配置
POSTGRES_VECTOR_INDEX_TYPE=HNSW
POSTGRES_HNSW_M=16
POSTGRES_HNSW_EF=200

# Embedding 配置
EMBEDDING_DIM=1024
COSINE_THRESHOLD=0.2
```

## 下一步

配置完成后：
1. 重启 LightRAG 服务器
2. 上传或重新处理文档
3. 向量数据会自动存储到 PostgreSQL
4. 使用 `/query` 接口测试向量检索功能

