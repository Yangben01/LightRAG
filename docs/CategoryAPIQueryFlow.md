# 分类API查询流程说明

## `/documents/list` 接口查询流程

### 1. 接口入口
- **路径**: `POST /documents/list`
- **位置**: `lightrag/api/routers/document_routes.py`

### 2. 查询流程

#### 步骤1: 获取所有状态的文档
```python
# 遍历所有文档状态
all_statuses = [
    DocStatus.PENDING,      # 待处理
    DocStatus.PROCESSING,   # 处理中
    DocStatus.PREPROCESSED, # 预处理完成
    DocStatus.PROCESSED,    # 处理完成
    DocStatus.FAILED,       # 处理失败
]

# 对每个状态调用 rag.get_docs_by_status(status)
for status in all_statuses:
    docs = await rag.get_docs_by_status(status)
```

#### 步骤2: 底层存储查询（根据配置的存储类型）

**PostgreSQL 存储** (`PGDocStatusStorage`):
```sql
SELECT * FROM LIGHTRAG_DOC_STATUS 
WHERE workspace = $1 AND status = $2
```
- 直接查询数据库表 `LIGHTRAG_DOC_STATUS`
- 使用 workspace 和 status 作为查询条件
- 返回该状态下的所有文档记录

**JSON 文件存储** (`JsonDocStatusStorage`):
- 从内存中的 `_data` 字典读取
- 遍历所有文档，筛选出匹配状态的文档
- 数据来源：`rag_storage/{workspace}/kv_store_doc_status.json`

**Redis 存储** (`RedisDocStatusStorage`):
- 使用 `SCAN` 命令遍历所有键
- 键格式：`{namespace}:{doc_id}`
- 获取值后解析 JSON，筛选匹配状态的文档

**MongoDB 存储** (`MongoDocStatusStorage`):
```javascript
db.collection.find({"status": status.value})
```
- 使用 MongoDB 的 find 查询
- 按 status 字段筛选

#### 步骤3: 内存中筛选和排序

获取所有文档后，在内存中进行：

1. **按分类筛选**（如果指定了 category_id）:
```python
if request.category_id:
    if not doc_status.metadata or doc_status.metadata.get('category_id') != request.category_id:
        continue  # 跳过不匹配的文档
```

2. **按文件名搜索**（如果指定了 search）:
```python
if request.search:
    search_lower = request.search.lower()
    if not doc_status.file_path or search_lower not in doc_status.file_path.lower():
        continue  # 跳过不匹配的文档
```

3. **排序**:
```python
# 根据 sort_field 和 sort_direction 排序
all_docs.sort(key=sort_key, reverse=reverse)
```

4. **分页**:
```python
start_idx = (request.page - 1) * request.page_size
end_idx = start_idx + request.page_size
paginated_docs = all_docs[start_idx:end_idx]
```

### 3. 数据存储位置

文档状态信息存储在 **DOC_STATUS_STORAGE** 中，根据配置不同：

| 存储类型 | 数据位置 | 查询方式 |
|---------|---------|---------|
| PostgreSQL | `LIGHTRAG_DOC_STATUS` 表 | SQL 查询 |
| JSON | `rag_storage/{workspace}/kv_store_doc_status.json` | 文件读取 + 内存筛选 |
| Redis | Redis 键值对 | SCAN + GET |
| MongoDB | MongoDB 集合 | find 查询 |

### 4. 分类信息存储

分类信息存储在文档的 `metadata` 字段中：
- **PostgreSQL**: `metadata` 字段（JSONB 类型）
- **JSON/Redis/MongoDB**: `metadata` 字段（JSON 对象）

分类定义本身存储在：
- **PostgreSQL**: `LIGHTRAG_CATEGORIES` 表
- **JSON**: `rag_storage/{workspace}/categories.json`（回退方案）

### 5. 查询性能说明

**当前实现的特点**：
- ✅ 支持多种存储后端
- ✅ 灵活的内存筛选（分类、搜索）
- ⚠️ 需要加载所有文档到内存（对于大数据量可能较慢）

**优化建议**（如果数据量很大）：
- PostgreSQL: 可以在数据库层面添加 WHERE 条件进行筛选
- MongoDB: 可以使用聚合管道在数据库层面筛选
- 添加数据库索引优化查询性能

### 6. 查询示例

**PostgreSQL 查询示例**：
```sql
-- 获取所有 PROCESSED 状态的文档
SELECT * FROM LIGHTRAG_DOC_STATUS 
WHERE workspace = 'space1' AND status = 'processed';

-- 如果要在数据库层面筛选分类（需要优化）
SELECT * FROM LIGHTRAG_DOC_STATUS 
WHERE workspace = 'space1' 
  AND status = 'processed'
  AND metadata->>'category_id' = 'cat_123456';
```

**当前实现**：
```python
# 1. 数据库查询（获取所有文档）
docs = await rag.get_docs_by_status(DocStatus.PROCESSED)
# 返回: {doc_id: DocProcessingStatus, ...}

# 2. 内存筛选（按分类）
for doc_id, doc_status in docs.items():
    if doc_status.metadata.get('category_id') == category_id:
        # 匹配的文档
```

### 7. 数据流图

```
客户端请求
    ↓
POST /documents/list
    ↓
get_documents_list()
    ↓
遍历所有状态 (PENDING, PROCESSING, ...)
    ↓
rag.get_docs_by_status(status)
    ↓
┌─────────────────────────────────┐
│ 根据存储类型查询                │
├─────────────────────────────────┤
│ PostgreSQL: SQL 查询            │
│ JSON: 文件读取                  │
│ Redis: SCAN + GET               │
│ MongoDB: find()                 │
└─────────────────────────────────┘
    ↓
返回所有文档 (dict[doc_id, DocProcessingStatus])
    ↓
内存筛选（分类、搜索）
    ↓
排序
    ↓
分页
    ↓
返回简化格式 (SimpleDocListResponse)
```

### 8. 优化方向

如果数据量很大，可以考虑：

1. **数据库层面筛选**（PostgreSQL/MongoDB）:
   - 在 SQL/MongoDB 查询中添加分类筛选条件
   - 减少内存中的数据处理量

2. **添加索引**:
   - PostgreSQL: 在 `metadata` 字段上创建 GIN 索引
   - MongoDB: 在 `metadata.category_id` 上创建索引

3. **缓存机制**:
   - 对常用分类的文档列表进行缓存
   - 减少重复查询

