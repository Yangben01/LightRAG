# 按文档查询实体数据

## 存储逻辑说明

在 PostgreSQL 中，实体和文档的关联关系如下：

### 表结构

1. **LIGHTRAG_VDB_CHUNKS** (文档分块表)
   - `id`: chunk ID
   - `full_doc_id`: 完整文档的 ID
   - `file_path`: 文档文件路径

2. **LIGHTRAG_VDB_ENTITY** (实体表)
   - `id`: 实体 ID
   - `entity_name`: 实体名称
   - `chunk_ids`: VARCHAR(255)[] - 关联的 chunk ID 数组
   - `file_path`: 文档文件路径（可选）

### 关联关系

- 实体通过 `chunk_ids` 数组关联到多个 chunks
- chunks 通过 `full_doc_id` 关联到文档
- 实体也可能直接存储 `file_path` 字段

## 查询方法对比

### 推荐方案：通过 full_doc_id 查询 ⭐

**优点**：
- ✅ **最准确**：`full_doc_id` 是文档的唯一标识符，不会重复
- ✅ **性能好**：可以直接在 `full_doc_id` 上建立索引
- ✅ **数据一致性强**：文档 ID 不会因为文件移动而改变
- ✅ **标准做法**：符合数据库设计规范（使用 ID 而非路径）

**适用场景**：
- 当你已知文档 ID 时（最常见情况）
- 需要精确查询特定文档的实体
- 生产环境推荐使用

### 方法1: 通过 full_doc_id 查询（推荐）

```sql
-- 查询指定文档的所有实体
SELECT DISTINCT
    e.id,
    e.entity_name,
    e.content,
    e.chunk_ids,
    e.file_path,
    e.create_time,
    e.update_time
FROM LIGHTRAG_VDB_ENTITY e
WHERE e.workspace = $1
  AND EXISTS (
      SELECT 1
      FROM LIGHTRAG_VDB_CHUNKS c
      WHERE c.workspace = $1
        AND c.full_doc_id = $2  -- 文档 ID
        AND c.id = ANY(e.chunk_ids)
  )
ORDER BY e.create_time DESC;
```

### 方法2: 通过 file_path 查询

**优点**：
- ✅ 直观：直接使用文件路径
- ✅ 适合用户界面展示

**缺点**：
- ⚠️ **可能不准确**：文件路径可能变化、重复或为空
- ⚠️ **性能较差**：路径字符串比较比 ID 比较慢
- ⚠️ **数据一致性风险**：文件移动后路径会变化

**适用场景**：
- 仅当不知道文档 ID 但知道文件路径时
- 临时查询或调试场景
- 不推荐在生产环境大量使用

```sql
-- 方式2.1: 通过实体的 file_path 字段查询
SELECT 
    e.id,
    e.entity_name,
    e.content,
    e.chunk_ids,
    e.file_path,
    e.create_time,
    e.update_time
FROM LIGHTRAG_VDB_ENTITY e
WHERE e.workspace = $1
  AND e.file_path = $2  -- 文档文件路径
ORDER BY e.create_time DESC;

-- 方式2.2: 通过 chunks 的 file_path 关联查询
SELECT DISTINCT
    e.id,
    e.entity_name,
    e.content,
    e.chunk_ids,
    e.file_path,
    e.create_time,
    e.update_time
FROM LIGHTRAG_VDB_ENTITY e
WHERE e.workspace = $1
  AND EXISTS (
      SELECT 1
      FROM LIGHTRAG_VDB_CHUNKS c
      WHERE c.workspace = $1
        AND c.file_path = $2  -- 文档文件路径
        AND c.id = ANY(e.chunk_ids)
  )
ORDER BY e.create_time DESC;
```

### 方法3: 组合查询

同时检查 `file_path` 和通过 `chunk_ids` 关联的 chunks：

**优点**：
- ✅ **最全面**：覆盖所有可能的关联方式
- ✅ **容错性强**：即使某些数据不完整也能查询到结果

**缺点**：
- ⚠️ **性能较差**：需要执行多个条件判断
- ⚠️ **复杂度高**：SQL 语句较复杂

**适用场景**：
- 数据迁移或数据清理场景
- 需要确保不遗漏任何关联实体
- 不推荐作为常规查询方法

```sql
-- 查询指定文档的所有实体（组合方式）
SELECT DISTINCT
    e.id,
    e.entity_name,
    e.content,
    e.chunk_ids,
    e.file_path,
    e.create_time,
    e.update_time
FROM LIGHTRAG_VDB_ENTITY e
WHERE e.workspace = $1
  AND (
      -- 方式1: 实体直接关联文档路径
      e.file_path = $2
      OR
      -- 方式2: 通过 chunks 关联文档
      EXISTS (
          SELECT 1
          FROM LIGHTRAG_VDB_CHUNKS c
          WHERE c.workspace = $1
            AND (
                c.file_path = $2  -- 通过 file_path
                OR c.full_doc_id = $3  -- 通过 full_doc_id
            )
            AND c.id = ANY(e.chunk_ids)
      )
  )
ORDER BY e.create_time DESC;
```

## 使用示例

### Python 代码示例

```python
async def get_entities_by_document(
    db: PostgreSQLDB,
    workspace: str,
    doc_id: str = None,
    file_path: str = None
) -> list[dict]:
    """
    按文档查询实体
    
    Args:
        db: PostgreSQL 数据库连接
        workspace: 工作空间
        doc_id: 文档 ID (full_doc_id)
        file_path: 文档文件路径
    
    Returns:
        实体列表
    """
    if doc_id:
        # 通过 full_doc_id 查询
        sql = """
        SELECT DISTINCT
            e.id,
            e.entity_name,
            e.content,
            e.chunk_ids,
            e.file_path,
            EXTRACT(EPOCH FROM e.create_time)::BIGINT as create_time,
            EXTRACT(EPOCH FROM e.update_time)::BIGINT as update_time
        FROM LIGHTRAG_VDB_ENTITY e
        WHERE e.workspace = $1
          AND EXISTS (
              SELECT 1
              FROM LIGHTRAG_VDB_CHUNKS c
              WHERE c.workspace = $1
                AND c.full_doc_id = $2
                AND c.id = ANY(e.chunk_ids)
          )
        ORDER BY e.create_time DESC;
        """
        params = [workspace, doc_id]
    elif file_path:
        # 通过 file_path 查询
        sql = """
        SELECT DISTINCT
            e.id,
            e.entity_name,
            e.content,
            e.chunk_ids,
            e.file_path,
            EXTRACT(EPOCH FROM e.create_time)::BIGINT as create_time,
            EXTRACT(EPOCH FROM e.update_time)::BIGINT as update_time
        FROM LIGHTRAG_VDB_ENTITY e
        WHERE e.workspace = $1
          AND (
              e.file_path = $2
              OR EXISTS (
                  SELECT 1
                  FROM LIGHTRAG_VDB_CHUNKS c
                  WHERE c.workspace = $1
                    AND c.file_path = $2
                    AND c.id = ANY(e.chunk_ids)
              )
          )
        ORDER BY e.create_time DESC;
        """
        params = [workspace, file_path]
    else:
        raise ValueError("必须提供 doc_id 或 file_path")
    
    results = await db.query(sql, params, multirows=True)
    return results
```

### 直接 SQL 查询示例

```sql
-- 示例1: 查询文档 ID 为 'doc-123' 的所有实体
SELECT DISTINCT
    e.entity_name,
    e.content,
    e.chunk_ids,
    e.file_path
FROM LIGHTRAG_VDB_ENTITY e
WHERE e.workspace = 'your_workspace'
  AND EXISTS (
      SELECT 1
      FROM LIGHTRAG_VDB_CHUNKS c
      WHERE c.workspace = 'your_workspace'
        AND c.full_doc_id = 'doc-123'
        AND c.id = ANY(e.chunk_ids)
  );

-- 示例2: 查询文件路径为 '/path/to/document.pdf' 的所有实体
SELECT DISTINCT
    e.entity_name,
    e.content,
    e.chunk_ids,
    e.file_path
FROM LIGHTRAG_VDB_ENTITY e
WHERE e.workspace = 'your_workspace'
  AND (
      e.file_path = '/path/to/document.pdf'
      OR EXISTS (
          SELECT 1
          FROM LIGHTRAG_VDB_CHUNKS c
          WHERE c.workspace = 'your_workspace'
            AND c.file_path = '/path/to/document.pdf'
            AND c.id = ANY(e.chunk_ids)
      )
  );
```

## 推荐方案总结

### 🎯 最佳实践

**优先使用 `full_doc_id` 查询**，原因：
1. **准确性最高**：文档 ID 是唯一标识，不会重复
2. **性能最优**：可以在 `full_doc_id` 上建立高效索引
3. **数据稳定**：文档 ID 不会因为文件移动而改变
4. **符合规范**：使用主键/外键关联是数据库设计最佳实践

### 使用建议

| 场景 | 推荐方法 | 原因 |
|------|---------|------|
| 正常业务查询 | `full_doc_id` | 准确、快速、稳定 |
| 用户界面展示 | `full_doc_id` + 显示 `file_path` | 查询用 ID，展示用路径 |
| 数据迁移/清理 | 组合查询 | 确保不遗漏数据 |
| 临时调试 | `file_path` | 快速验证，但需注意准确性 |

## 注意事项

1. **chunk_ids 数组查询**: PostgreSQL 使用 `ANY(array)` 来检查数组是否包含某个值
2. **性能优化**: 如果经常按文档查询，**必须**在 `LIGHTRAG_VDB_CHUNKS.full_doc_id` 上创建索引（这是最重要的索引）
3. **数据一致性**: 确保实体的 `chunk_ids` 数组中的 chunk 确实存在于 `LIGHTRAG_VDB_CHUNKS` 表中
4. **workspace 隔离**: 所有查询都必须包含 `workspace` 条件以确保多租户数据隔离
5. **file_path 的局限性**: `file_path` 字段可能为空（NULL），且同一文档在不同时间可能有不同路径

## API 接口使用

### 新增 API 端点

已添加 `/entities/by-document` API 接口，支持通过文档 ID 或文件路径查询实体。

#### 接口信息

- **路径**: `GET /entities/by-document`
- **认证**: 需要 API Key（通过请求头或查询参数）
- **多租户**: 支持通过 `LIGHTRAG-WORKSPACE` 请求头指定工作空间

#### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `doc_id` | string | 否* | 文档 ID (full_doc_id)，推荐使用 |
| `file_path` | string | 否* | 文档文件路径，备选方式 |
| `page` | integer | 否 | 页码，从1开始（默认：1） |
| `page_size` | integer | 否 | 每页数量，最大500（默认：50） |

*注：`doc_id` 和 `file_path` 至少需要提供一个

#### 响应示例

```json
{
  "status": "success",
  "doc_id": "doc-123",
  "file_path": null,
  "total": 25,
  "page": 1,
  "page_size": 20,
  "entities_count": 20,
  "entities": [
    {
      "id": "ent-abc123",
      "entity_name": "特斯拉",
      "content": "特斯拉是一家电动汽车公司...",
      "chunk_ids": ["chunk-1", "chunk-2"],
      "file_path": "/path/to/document.pdf",
      "create_time": 1704067200,
      "update_time": 1704067200
    }
  ]
}
```

**响应字段说明**：
- `status`: 请求状态
- `doc_id`: 查询使用的文档 ID
- `file_path`: 查询使用的文件路径（如果使用 doc_id 则为 null）
- `total`: 符合条件的实体总数
- `page`: 当前页码
- `page_size`: 每页数量
- `entities_count`: 当前页返回的实体数量
- `entities`: 实体列表

#### 使用示例

```bash
# 通过文档 ID 查询（推荐，带分页）
curl -X GET "http://localhost:8020/entities/by-document?doc_id=doc-123&page=1&page_size=20" \
  -H "LIGHTRAG-WORKSPACE: my_workspace" \
  -H "Authorization: Bearer your-api-key"

# 通过文件路径查询（带分页）
curl -X GET "http://localhost:8020/entities/by-document?file_path=/path/to/document.pdf&page=1&page_size=20" \
  -H "LIGHTRAG-WORKSPACE: my_workspace" \
  -H "Authorization: Bearer your-api-key"

# 查询第二页
curl -X GET "http://localhost:8020/entities/by-document?doc_id=doc-123&page=2&page_size=20" \
  -H "LIGHTRAG-WORKSPACE: my_workspace" \
  -H "Authorization: Bearer your-api-key"
```

**分页说明**：
- 使用 `page` 参数指定页码（从1开始）
- 使用 `page_size` 参数指定每页数量（最大500，默认50）
- 响应中包含 `total` 字段，表示符合条件的实体总数
- 可以通过 `total` 和 `page_size` 计算总页数：`总页数 = ceil(total / page_size)`

#### 注意事项

1. **存储后端要求**: 此接口仅在使用 PostgreSQL 向量存储（`PGVectorStorage`）时可用
2. **性能优化**: 建议在 `LIGHTRAG_VDB_CHUNKS.full_doc_id` 上创建索引
3. **推荐使用 `doc_id`**: 比 `file_path` 更准确、快速、稳定

## 索引建议

### 必需索引（强烈推荐）

```sql
-- ⭐ 最重要：为 full_doc_id 创建索引（必需）
CREATE INDEX IF NOT EXISTS idx_vdb_chunks_full_doc_id 
ON LIGHTRAG_VDB_CHUNKS(workspace, full_doc_id);

-- ⭐ 重要：为 chunk_ids 数组创建 GIN 索引以优化数组查询（必需）
CREATE INDEX IF NOT EXISTS idx_vdb_entity_chunk_ids 
ON LIGHTRAG_VDB_ENTITY USING GIN(chunk_ids);
```

### 可选索引（根据使用情况）

```sql
-- 如果经常使用 file_path 查询，可以创建（但优先级较低）
CREATE INDEX IF NOT EXISTS idx_vdb_chunks_file_path 
ON LIGHTRAG_VDB_CHUNKS(workspace, file_path)
WHERE file_path IS NOT NULL;  -- 只索引非空值

CREATE INDEX IF NOT EXISTS idx_vdb_entity_file_path 
ON LIGHTRAG_VDB_ENTITY(workspace, file_path)
WHERE file_path IS NOT NULL;  -- 只索引非空值
```

### 索引优先级说明

1. **idx_vdb_chunks_full_doc_id** - 最高优先级，用于通过文档 ID 查找 chunks
2. **idx_vdb_entity_chunk_ids** - 高优先级，用于检查实体是否包含某个 chunk ID
3. **file_path 索引** - 低优先级，仅在确实需要按路径查询时创建

