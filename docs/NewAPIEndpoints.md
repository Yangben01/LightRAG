# 新增 API 接口文档

本文档描述了为满足实体库、关系库和文档切片查看需求而新增的 API 接口。

## 📋 目录

- [实体管理接口](#实体管理接口)
- [关系管理接口](#关系管理接口)
- [文档分块接口](#文档分块接口)
- [使用示例](#使用示例)

---

## 实体管理接口

### 1. 获取实体列表

**接口路径**: `GET /entities/list`

**功能描述**: 获取知识图谱中的所有实体，支持分页和按类型筛选

**请求参数**:

| 参数名      | 类型   | 必填 | 说明                                              | 默认值 |
| ----------- | ------ | ---- | ------------------------------------------------- | ------ |
| page        | int    | 否   | 页码（从 1 开始）                                 | 1      |
| page_size   | int    | 否   | 每页数量（1-500）                                 | 50     |
| entity_type | string | 否   | 实体类型筛选（如 PERSON, ORGANIZATION, LOCATION） | -      |
| search      | string | 否   | 搜索实体名称（模糊匹配）                          | -      |

**响应示例**:

```json
{
  "total": 150,
  "page": 1,
  "page_size": 50,
  "entities": [
    {
      "entity_name": "特斯拉",
      "entity_id": "特斯拉",
      "entity_type": "ORGANIZATION",
      "description": "电动汽车制造商",
      "source_id": "chunk-123<SEP>chunk-456",
      "degree": 15
    }
  ]
}
```

**字段说明**:

- `total`: 总实体数量
- `page`: 当前页码
- `page_size`: 每页数量
- `entities`: 实体列表
  - `entity_name`: 实体名称
  - `entity_id`: 实体 ID（通常与 entity_name 相同）
  - `entity_type`: 实体类型
  - `description`: 实体描述
  - `source_id`: 来源 chunk ID（用`<SEP>`分隔）
  - `degree`: 节点度数（连接数）

---

### 2. 获取实体详情

**接口路径**: `GET /entities/{entity_name}`

**功能描述**: 获取指定实体的详细信息，包括所有属性和关系网络

**路径参数**:

| 参数名      | 类型   | 必填 | 说明     |
| ----------- | ------ | ---- | -------- |
| entity_name | string | 是   | 实体名称 |

**响应示例**:

```json
{
  "status": "success",
  "entity": {
    "entity_name": "特斯拉",
    "entity_id": "特斯拉",
    "entity_type": "ORGANIZATION",
    "description": "电动汽车制造商",
    "source_id": "chunk-123<SEP>chunk-456",
    "degree": 15
  },
  "relations": [
    {
      "source_entity": "马斯克",
      "target_entity": "特斯拉",
      "description": "马斯克是特斯拉的CEO",
      "keywords": "CEO, 创始人",
      "weight": 1.0,
      "source_id": "chunk-123"
    }
  ],
  "relations_count": 15
}
```

**错误响应**:

- `404 Not Found`: 实体不存在

---

### 3. 获取实体的所有关系

**接口路径**: `GET /entities/{entity_name}/relations`

**功能描述**: 获取指定实体的所有关系列表

**路径参数**:

| 参数名      | 类型   | 必填 | 说明     |
| ----------- | ------ | ---- | -------- |
| entity_name | string | 是   | 实体名称 |

**响应示例**:

```json
{
  "status": "success",
  "entity_name": "特斯拉",
  "relations_count": 15,
  "relations": [
    {
      "source_entity": "马斯克",
      "target_entity": "特斯拉",
      "description": "马斯克是特斯拉的CEO",
      "keywords": "CEO, 创始人",
      "weight": 1.0,
      "source_id": "chunk-123"
    }
  ]
}
```

---

## 关系管理接口

### 4. 获取关系列表

**接口路径**: `GET /relations/list`

**功能描述**: 获取知识图谱中的所有关系，支持分页和筛选

**请求参数**:

| 参数名      | 类型   | 必填 | 说明                                       | 默认值 |
| ----------- | ------ | ---- | ------------------------------------------ | ------ |
| page        | int    | 否   | 页码（从 1 开始）                          | 1      |
| page_size   | int    | 否   | 每页数量（1-500）                          | 50     |
| keyword     | string | 否   | 关系关键词筛选（模糊匹配）                 | -      |
| entity_name | string | 否   | 按实体名称筛选，返回与该实体相关的所有关系 | -      |

**响应示例**:

```json
{
  "total": 300,
  "page": 1,
  "page_size": 50,
  "relations": [
    {
      "source_entity": "马斯克",
      "target_entity": "特斯拉",
      "description": "马斯克是特斯拉的CEO",
      "keywords": "CEO, 创始人",
      "weight": 1.0,
      "source_id": "chunk-123"
    }
  ]
}
```

**字段说明**:

- `total`: 总关系数量
- `page`: 当前页码
- `page_size`: 每页数量
- `relations`: 关系列表
  - `source_entity`: 源实体名称
  - `target_entity`: 目标实体名称
  - `description`: 关系描述
  - `keywords`: 关系关键词
  - `weight`: 关系权重
  - `source_id`: 来源 chunk ID

---

## 文档分块接口

### 5. 获取所有文档分块列表

**接口路径**: `GET /chunks/list`

**功能描述**: 获取所有文档分块(chunk)，支持分页和按文档筛选

**请求参数**:

| 参数名    | 类型   | 必填 | 说明              | 默认值 |
| --------- | ------ | ---- | ----------------- | ------ |
| page      | int    | 否   | 页码（从 1 开始） | 1      |
| page_size | int    | 否   | 每页数量（1-500） | 50     |
| doc_id    | string | 否   | 按文档 ID 筛选    | -      |

**响应示例**:

```json
{
  "total": 500,
  "page": 1,
  "page_size": 50,
  "chunks": [
    {
      "chunk_id": "chunk-001",
      "content": "特斯拉是一家电动汽车制造商...",
      "tokens": 256,
      "full_doc_id": "doc-001",
      "chunk_order_index": 0
    }
  ]
}
```

**字段说明**:

- `total`: 总 chunk 数量
- `page`: 当前页码
- `page_size`: 每页数量
- `chunks`: chunk 列表
  - `chunk_id`: chunk ID
  - `content`: chunk 内容
  - `tokens`: token 数量
  - `full_doc_id`: 所属文档 ID
  - `chunk_order_index`: chunk 顺序索引

**注意**: 此接口目前仅支持 JSON 存储后端。对于其他存储后端（如 PostgreSQL、MongoDB），会返回 `501 Not Implemented` 错误。

---

### 6. 获取 chunk 详情

**接口路径**: `GET /chunks/{chunk_id}`

**功能描述**: 获取指定 chunk 的详细信息，包括内容和关联的实体、关系

**路径参数**:

| 参数名   | 类型   | 必填 | 说明     |
| -------- | ------ | ---- | -------- |
| chunk_id | string | 是   | Chunk ID |

**响应示例**:

```json
{
  "status": "success",
  "chunk": {
    "chunk_id": "chunk-001",
    "content": "特斯拉是一家电动汽车制造商，由马斯克领导...",
    "tokens": 256,
    "full_doc_id": "doc-001",
    "chunk_order_index": 0
  },
  "entities": [
    {
      "entity_name": "特斯拉",
      "entity_type": "ORGANIZATION",
      "description": "电动汽车制造商"
    },
    {
      "entity_name": "马斯克",
      "entity_type": "PERSON",
      "description": "企业家"
    }
  ],
  "entities_count": 2,
  "relations": [
    {
      "source_entity": "马斯克",
      "target_entity": "特斯拉",
      "description": "马斯克是特斯拉的CEO",
      "keywords": "CEO, 创始人",
      "weight": 1.0
    }
  ],
  "relations_count": 1
}
```

**字段说明**:

- `chunk`: chunk 详细信息
- `entities`: 在此 chunk 中提取的实体列表
- `entities_count`: 实体数量
- `relations`: 在此 chunk 中提取的关系列表
- `relations_count`: 关系数量

**错误响应**:

- `404 Not Found`: Chunk 不存在

---

### 7. 获取文档的所有 chunks

**接口路径**: `GET /documents/{doc_id}/chunks`

**功能描述**: 获取指定文档的所有分块（按顺序排序）

**路径参数**:

| 参数名 | 类型   | 必填 | 说明    |
| ------ | ------ | ---- | ------- |
| doc_id | string | 是   | 文档 ID |

**响应示例**:

```json
{
  "status": "success",
  "doc_id": "doc-001",
  "chunks_count": 10,
  "chunks": [
    {
      "chunk_id": "chunk-001",
      "content": "特斯拉是一家电动汽车制造商...",
      "tokens": 256,
      "chunk_order_index": 0
    },
    {
      "chunk_id": "chunk-002",
      "content": "该公司成立于2003年...",
      "tokens": 180,
      "chunk_order_index": 1
    }
  ]
}
```

**字段说明**:

- `doc_id`: 文档 ID
- `chunks_count`: chunk 数量
- `chunks`: chunk 列表（按 chunk_order_index 排序）

**错误响应**:

- `404 Not Found`: 文档不存在（当没有找到 chunks 且文档也不存在时）

---

## 使用示例

### Python 示例

```python
import requests

# 配置
BASE_URL = "http://localhost:9621"
API_KEY = "your-api-key"  # 如果启用了API认证

headers = {}
if API_KEY:
    headers["Authorization"] = f"Bearer {API_KEY}"

# 1. 获取所有PERSON类型的实体
response = requests.get(
    f"{BASE_URL}/entities/list",
    params={"entity_type": "PERSON", "page": 1, "page_size": 10},
    headers=headers
)
entities = response.json()
print(f"找到 {entities['total']} 个人物实体")

# 2. 获取特定实体的详情
entity_name = "马斯克"
response = requests.get(
    f"{BASE_URL}/entities/{entity_name}",
    headers=headers
)
entity_detail = response.json()
print(f"实体 '{entity_name}' 有 {entity_detail['relations_count']} 个关系")

# 3. 获取包含"CEO"关键词的关系
response = requests.get(
    f"{BASE_URL}/relations/list",
    params={"keyword": "CEO", "page": 1, "page_size": 20},
    headers=headers
)
relations = response.json()
print(f"找到 {relations['total']} 个包含'CEO'的关系")

# 4. 获取文档的所有chunks
doc_id = "doc-001"
response = requests.get(
    f"{BASE_URL}/documents/{doc_id}/chunks",
    headers=headers
)
doc_chunks = response.json()
print(f"文档 '{doc_id}' 被分成了 {doc_chunks['chunks_count']} 个chunks")

# 5. 获取chunk详情（包括关联的实体和关系）
chunk_id = "chunk-001"
response = requests.get(
    f"{BASE_URL}/chunks/{chunk_id}",
    headers=headers
)
chunk_detail = response.json()
print(f"Chunk包含 {chunk_detail['entities_count']} 个实体和 {chunk_detail['relations_count']} 个关系")
```

### cURL 示例

```bash
# 1. 获取实体列表
curl -X GET "http://localhost:9621/entities/list?page=1&page_size=10&entity_type=PERSON" \
  -H "Authorization: Bearer your-api-key"

# 2. 获取实体详情
curl -X GET "http://localhost:9621/entities/马斯克" \
  -H "Authorization: Bearer your-api-key"

# 3. 获取关系列表
curl -X GET "http://localhost:9621/relations/list?keyword=CEO&page=1&page_size=20" \
  -H "Authorization: Bearer your-api-key"

# 4. 获取文档chunks
curl -X GET "http://localhost:9621/documents/doc-001/chunks" \
  -H "Authorization: Bearer your-api-key"

# 5. 获取chunk详情
curl -X GET "http://localhost:9621/chunks/chunk-001" \
  -H "Authorization: Bearer your-api-key"
```

### JavaScript 示例

```javascript
const BASE_URL = "http://localhost:9621";
const API_KEY = "your-api-key";

const headers = {
  Authorization: `Bearer ${API_KEY}`,
};

// 1. 获取实体列表
async function getEntities() {
  const response = await fetch(
    `${BASE_URL}/entities/list?entity_type=PERSON&page=1&page_size=10`,
    { headers }
  );
  const data = await response.json();
  console.log(`找到 ${data.total} 个人物实体`);
  return data;
}

// 2. 获取实体详情
async function getEntityDetail(entityName) {
  const response = await fetch(
    `${BASE_URL}/entities/${encodeURIComponent(entityName)}`,
    { headers }
  );
  const data = await response.json();
  console.log(`实体 '${entityName}' 有 ${data.relations_count} 个关系`);
  return data;
}

// 3. 获取关系列表
async function getRelations(keyword) {
  const response = await fetch(
    `${BASE_URL}/relations/list?keyword=${encodeURIComponent(
      keyword
    )}&page=1&page_size=20`,
    { headers }
  );
  const data = await response.json();
  console.log(`找到 ${data.total} 个包含'${keyword}'的关系`);
  return data;
}

// 4. 获取文档chunks
async function getDocumentChunks(docId) {
  const response = await fetch(
    `${BASE_URL}/documents/${encodeURIComponent(docId)}/chunks`,
    { headers }
  );
  const data = await response.json();
  console.log(`文档 '${docId}' 被分成了 ${data.chunks_count} 个chunks`);
  return data;
}

// 5. 获取chunk详情
async function getChunkDetail(chunkId) {
  const response = await fetch(
    `${BASE_URL}/chunks/${encodeURIComponent(chunkId)}`,
    { headers }
  );
  const data = await response.json();
  console.log(
    `Chunk包含 ${data.entities_count} 个实体和 ${data.relations_count} 个关系`
  );
  return data;
}

// 使用示例
(async () => {
  await getEntities();
  await getEntityDetail("马斯克");
  await getRelations("CEO");
  await getDocumentChunks("doc-001");
  await getChunkDetail("chunk-001");
})();
```

---

## 注意事项

1. **存储后端限制**:

   - Chunk 相关接口目前仅支持 JSON 存储后端
   - 如果使用 PostgreSQL、MongoDB 等其他存储后端，需要实现相应的遍历方法

2. **性能考虑**:

   - 实体和关系列表接口会加载所有数据到内存进行过滤和分页
   - 对于大型知识图谱（>10 万实体），建议使用较小的 page_size
   - 考虑在前端实现增量加载或虚拟滚动

3. **权限控制**:

   - 所有接口都遵循 LightRAG 的认证机制
   - 如果启用了 API_KEY，需要在请求头中携带正确的 token

4. **字符编码**:

   - 实体名称可能包含中文或特殊字符
   - 在 URL 中使用实体名称时需要进行 URL 编码

5. **关系方向**:
   - 知识图谱中的关系是无向的
   - 返回的关系数据中，source 和 target 顺序可能与创建时不同

---

## API 文档访问

启动 LightRAG 服务后，可以通过以下方式访问完整的 API 文档：

- **Swagger UI**: `http://localhost:9621/docs`
- **ReDoc**: `http://localhost:9621/redoc`

这些交互式文档提供了所有接口的详细说明和测试功能。

---

## 更新日志

- **v1.0** (2025-12-04): 初始版本，添加实体、关系和 chunk 管理接口
