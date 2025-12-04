# 新 API 接口快速入门指南

本指南将帮助你快速开始使用新增的实体、关系和 chunk 管理 API 接口。

## 🚀 快速测试（5 分钟上手）

### 步骤 1: 启动服务

```bash
# 进入项目目录
cd /Users/yangben/Documents/yangben_privacy/LightRAG

# 启动 LightRAG 服务器
lightrag-server

# 或使用 uvicorn
uvicorn lightrag.api.lightrag_server:app --reload --port 8020
```

等待看到以下输出：

```
Server is ready to accept connections! 🚀
```

### 步骤 2: 访问交互式文档

打开浏览器访问: http://localhost:8020/docs

你会看到新增的接口分组：

- 📦 **entities-relations**: 实体和关系管理
- 📄 **chunks**: 文档分块管理

### 步骤 3: 在浏览器中测试

#### 测试 1: 获取实体列表

1. 在 Swagger UI 中找到 `GET /entities/list`
2. 点击 "Try it out"
3. 设置参数：
   - page: 1
   - page_size: 10
4. 点击 "Execute"
5. 查看响应

#### 测试 2: 搜索特定类型的实体

1. 找到 `GET /entities/list`
2. 设置参数：
   - entity_type: `PERSON` (或 `ORGANIZATION`, `LOCATION`)
   - page: 1
   - page_size: 20
3. 点击 "Execute"
4. 只会返回该类型的实体

#### 测试 3: 获取实体详情

1. 从上一步获取一个实体名称，例如 "特斯拉"
2. 找到 `GET /entities/{entity_name}`
3. 在 entity_name 输入框中输入实体名称
4. 点击 "Execute"
5. 查看该实体的所有信息和关系

#### 测试 4: 获取关系列表

1. 找到 `GET /relations/list`
2. 点击 "Try it out"
3. 设置参数：
   - page: 1
   - page_size: 20
4. 点击 "Execute"
5. 查看所有关系

#### 测试 5: 获取文档 chunks

1. 找到 `GET /chunks/list`
2. 点击 "Try it out"
3. 点击 "Execute"
4. 查看所有文档分块

---

## 💻 命令行测试（使用 curl）

### 获取实体列表

```bash
curl "http://localhost:8020/entities/list?page=1&page_size=10" | jq
```

### 搜索实体

```bash
curl "http://localhost:8020/entities/list?search=特斯拉" | jq
```

### 按类型筛选实体

```bash
curl "http://localhost:8020/entities/list?entity_type=PERSON&page=1&page_size=20" | jq
```

### 获取实体详情（需要 URL 编码）

```bash
# 对于中文实体名，需要进行URL编码
entity_name="特斯拉"
encoded_name=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$entity_name'))")
curl "http://localhost:8020/entities/$encoded_name" | jq
```

### 获取实体的所有关系

```bash
curl "http://localhost:8020/entities/特斯拉/relations" | jq
```

### 获取关系列表

```bash
curl "http://localhost:8020/relations/list?page=1&page_size=20" | jq
```

### 按关键词搜索关系

```bash
curl "http://localhost:8020/relations/list?keyword=CEO" | jq
```

### 获取特定实体的关系

```bash
curl "http://localhost:8020/relations/list?entity_name=特斯拉" | jq
```

### 获取 chunks 列表

```bash
curl "http://localhost:8020/chunks/list?page=1&page_size=10" | jq
```

### 获取特定文档的 chunks

```bash
# 首先获取一个文档ID
doc_id=$(curl -s "http://localhost:8020/chunks/list?page=1&page_size=1" | jq -r '.chunks[0].full_doc_id')

# 获取该文档的所有chunks
curl "http://localhost:8020/documents/$doc_id/chunks" | jq
```

### 获取 chunk 详情

```bash
# 首先获取一个chunk ID
chunk_id=$(curl -s "http://localhost:8020/chunks/list?page=1&page_size=1" | jq -r '.chunks[0].chunk_id')

# 获取chunk详情
curl "http://localhost:8020/chunks/$chunk_id" | jq
```

---

## 🐍 Python 脚本测试

创建一个测试脚本 `test_new_apis.py`：

```python
#!/usr/bin/env python3
"""测试新增的API接口"""

import requests
import json
from urllib.parse import quote

BASE_URL = "http://localhost:8020"

def print_json(data):
    """美化打印JSON"""
    print(json.dumps(data, indent=2, ensure_ascii=False))

def test_entities_list():
    """测试获取实体列表"""
    print("\n" + "="*60)
    print("测试 1: 获取实体列表")
    print("="*60)

    response = requests.get(f"{BASE_URL}/entities/list?page=1&page_size=5")
    data = response.json()

    print(f"状态码: {response.status_code}")
    print(f"总实体数: {data['total']}")
    print(f"当前页: {data['page']}")
    print(f"每页数量: {data['page_size']}")
    print(f"\n前 {len(data['entities'])} 个实体:")
    for entity in data['entities']:
        print(f"  - {entity['entity_name']} ({entity['entity_type']}) - 度数: {entity['degree']}")

    return data['entities'][0]['entity_name'] if data['entities'] else None

def test_entity_detail(entity_name):
    """测试获取实体详情"""
    print("\n" + "="*60)
    print(f"测试 2: 获取实体详情 - {entity_name}")
    print("="*60)

    encoded_name = quote(entity_name)
    response = requests.get(f"{BASE_URL}/entities/{encoded_name}")

    if response.status_code == 200:
        data = response.json()
        print(f"状态码: {response.status_code}")
        print(f"实体名称: {data['entity']['entity_name']}")
        print(f"实体类型: {data['entity']['entity_type']}")
        print(f"描述: {data['entity']['description'][:100]}...")
        print(f"关系数量: {data['relations_count']}")
        print(f"\n前 3 个关系:")
        for rel in data['relations'][:3]:
            print(f"  - {rel['source_entity']} -> {rel['target_entity']}")
            print(f"    描述: {rel['description'][:80]}...")
    else:
        print(f"错误: {response.status_code}")

def test_entity_filter():
    """测试按类型筛选实体"""
    print("\n" + "="*60)
    print("测试 3: 按类型筛选实体 (PERSON)")
    print("="*60)

    response = requests.get(f"{BASE_URL}/entities/list?entity_type=PERSON&page=1&page_size=5")
    data = response.json()

    print(f"状态码: {response.status_code}")
    print(f"PERSON类型实体总数: {data['total']}")
    print(f"\n找到的实体:")
    for entity in data['entities']:
        print(f"  - {entity['entity_name']} ({entity['entity_type']})")

def test_relations_list():
    """测试获取关系列表"""
    print("\n" + "="*60)
    print("测试 4: 获取关系列表")
    print("="*60)

    response = requests.get(f"{BASE_URL}/relations/list?page=1&page_size=5")
    data = response.json()

    print(f"状态码: {response.status_code}")
    print(f"总关系数: {data['total']}")
    print(f"\n前 {len(data['relations'])} 个关系:")
    for rel in data['relations']:
        print(f"  - {rel['source_entity']} <-> {rel['target_entity']}")
        print(f"    关键词: {rel['keywords']}")
        print(f"    权重: {rel['weight']}")

def test_chunks_list():
    """测试获取chunks列表"""
    print("\n" + "="*60)
    print("测试 5: 获取chunks列表")
    print("="*60)

    response = requests.get(f"{BASE_URL}/chunks/list?page=1&page_size=3")

    if response.status_code == 200:
        data = response.json()
        print(f"状态码: {response.status_code}")
        print(f"总chunk数: {data['total']}")
        print(f"\n前 {len(data['chunks'])} 个chunks:")
        for chunk in data['chunks']:
            print(f"  - Chunk ID: {chunk['chunk_id']}")
            print(f"    文档ID: {chunk['full_doc_id']}")
            print(f"    Token数: {chunk['tokens']}")
            print(f"    内容预览: {chunk['content'][:80]}...")

        return data['chunks'][0]['chunk_id'] if data['chunks'] else None
    elif response.status_code == 501:
        print("当前存储后端不支持chunks列表查询")
        return None
    else:
        print(f"错误: {response.status_code}")
        return None

def test_chunk_detail(chunk_id):
    """测试获取chunk详情"""
    if not chunk_id:
        return

    print("\n" + "="*60)
    print(f"测试 6: 获取chunk详情 - {chunk_id}")
    print("="*60)

    encoded_id = quote(chunk_id)
    response = requests.get(f"{BASE_URL}/chunks/{encoded_id}")

    if response.status_code == 200:
        data = response.json()
        print(f"状态码: {response.status_code}")
        print(f"Chunk ID: {data['chunk']['chunk_id']}")
        print(f"Token数: {data['chunk']['tokens']}")
        print(f"内容长度: {len(data['chunk']['content'])} 字符")
        print(f"关联实体数: {data['entities_count']}")
        print(f"关联关系数: {data['relations_count']}")

        if data['entities']:
            print(f"\n关联的实体:")
            for entity in data['entities'][:3]:
                print(f"  - {entity['entity_name']} ({entity['entity_type']})")
    else:
        print(f"错误: {response.status_code}")

def main():
    """运行所有测试"""
    print("\n🚀 开始测试新增的API接口...")

    try:
        # 测试实体相关接口
        entity_name = test_entities_list()
        if entity_name:
            test_entity_detail(entity_name)
        test_entity_filter()

        # 测试关系接口
        test_relations_list()

        # 测试chunks接口
        chunk_id = test_chunks_list()
        test_chunk_detail(chunk_id)

        print("\n" + "="*60)
        print("✅ 所有测试完成!")
        print("="*60)

    except requests.exceptions.ConnectionError:
        print("\n❌ 错误: 无法连接到服务器")
        print("请确保 LightRAG 服务器正在运行:")
        print("  lightrag-server")
        print("  或")
        print("  uvicorn lightrag.api.lightrag_server:app --reload")
    except Exception as e:
        print(f"\n❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
```

运行测试：

```bash
chmod +x test_new_apis.py
python3 test_new_apis.py
```

---

## 🌐 Web 前端集成示例

### React/TypeScript 示例

```typescript
// api.ts - API客户端
import axios from "axios";

const BASE_URL = "http://localhost:8020";

// 如果需要认证
const api = axios.create({
  baseURL: BASE_URL,
  headers: {
    Authorization: `Bearer ${localStorage.getItem("api_token")}`,
  },
});

// 实体相关API
export const entitiesAPI = {
  // 获取实体列表
  list: (params: {
    page?: number;
    page_size?: number;
    entity_type?: string;
    search?: string;
  }) => api.get("/entities/list", { params }),

  // 获取实体详情
  detail: (entityName: string) =>
    api.get(`/entities/${encodeURIComponent(entityName)}`),

  // 获取实体关系
  relations: (entityName: string) =>
    api.get(`/entities/${encodeURIComponent(entityName)}/relations`),
};

// 关系相关API
export const relationsAPI = {
  list: (params: {
    page?: number;
    page_size?: number;
    keyword?: string;
    entity_name?: string;
  }) => api.get("/relations/list", { params }),
};

// Chunks相关API
export const chunksAPI = {
  // 获取chunks列表
  list: (params: { page?: number; page_size?: number; doc_id?: string }) =>
    api.get("/chunks/list", { params }),

  // 获取chunk详情
  detail: (chunkId: string) =>
    api.get(`/chunks/${encodeURIComponent(chunkId)}`),

  // 获取文档的所有chunks
  byDocument: (docId: string) =>
    api.get(`/documents/${encodeURIComponent(docId)}/chunks`),
};
```

### React 组件示例

```typescript
// EntityList.tsx - 实体列表组件
import React, { useEffect, useState } from "react";
import { entitiesAPI } from "./api";

interface Entity {
  entity_name: string;
  entity_type: string;
  description: string;
  degree: number;
}

export const EntityList: React.FC = () => {
  const [entities, setEntities] = useState<Entity[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [entityType, setEntityType] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    loadEntities();
  }, [page, entityType]);

  const loadEntities = async () => {
    setLoading(true);
    try {
      const response = await entitiesAPI.list({
        page,
        page_size: 20,
        entity_type: entityType || undefined,
      });
      setEntities(response.data.entities);
      setTotal(response.data.total);
    } catch (error) {
      console.error("加载实体失败:", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h1>实体列表 (共 {total} 个)</h1>

      {/* 类型筛选 */}
      <select
        value={entityType}
        onChange={(e) => setEntityType(e.target.value)}
      >
        <option value="">全部类型</option>
        <option value="PERSON">人物</option>
        <option value="ORGANIZATION">组织</option>
        <option value="LOCATION">地点</option>
      </select>

      {/* 实体列表 */}
      {loading ? (
        <div>加载中...</div>
      ) : (
        <table>
          <thead>
            <tr>
              <th>名称</th>
              <th>类型</th>
              <th>描述</th>
              <th>连接数</th>
            </tr>
          </thead>
          <tbody>
            {entities.map((entity) => (
              <tr key={entity.entity_name}>
                <td>{entity.entity_name}</td>
                <td>{entity.entity_type}</td>
                <td>{entity.description.substring(0, 100)}...</td>
                <td>{entity.degree}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* 分页 */}
      <div>
        <button disabled={page === 1} onClick={() => setPage(page - 1)}>
          上一页
        </button>
        <span>第 {page} 页</span>
        <button disabled={page * 20 >= total} onClick={() => setPage(page + 1)}>
          下一页
        </button>
      </div>
    </div>
  );
};
```

---

## 📊 常见使用场景

### 场景 1: 知识图谱浏览器

```python
def browse_knowledge_graph():
    """浏览知识图谱"""
    # 1. 获取所有实体类型统计
    all_entities = requests.get(f"{BASE_URL}/entities/list?page_size=500").json()
    type_counts = {}
    for entity in all_entities['entities']:
        entity_type = entity['entity_type']
        type_counts[entity_type] = type_counts.get(entity_type, 0) + 1

    print("实体类型统计:")
    for type_name, count in sorted(type_counts.items()):
        print(f"  {type_name}: {count}")
```

### 场景 2: 实体关系可视化

```python
def visualize_entity_relations(entity_name):
    """可视化实体关系"""
    response = requests.get(f"{BASE_URL}/entities/{entity_name}")
    data = response.json()

    # 构建图数据
    nodes = [{"id": entity_name, "label": entity_name}]
    edges = []

    for rel in data['relations']:
        target = rel['target_entity']
        nodes.append({"id": target, "label": target})
        edges.append({
            "from": rel['source_entity'],
            "to": target,
            "label": rel['keywords']
        })

    return {"nodes": nodes, "edges": edges}
```

### 场景 3: 文档内容分析

```python
def analyze_document(doc_id):
    """分析文档内容"""
    # 获取文档的所有chunks
    chunks = requests.get(f"{BASE_URL}/documents/{doc_id}/chunks").json()

    # 统计信息
    total_tokens = sum(chunk['tokens'] for chunk in chunks['chunks'])

    # 获取所有关联实体
    all_entities = set()
    for chunk in chunks['chunks']:
        chunk_detail = requests.get(f"{BASE_URL}/chunks/{chunk['chunk_id']}").json()
        for entity in chunk_detail['entities']:
            all_entities.add(entity['entity_name'])

    print(f"文档 {doc_id}:")
    print(f"  总chunks: {chunks['chunks_count']}")
    print(f"  总tokens: {total_tokens}")
    print(f"  涉及实体: {len(all_entities)}")
```

---

## ✅ 验证清单

测试完成后，确认以下功能正常：

- [ ] 实体列表可以正常获取
- [ ] 实体按类型筛选工作正常
- [ ] 实体搜索功能正常
- [ ] 实体详情可以查看
- [ ] 实体关系网络完整显示
- [ ] 关系列表可以正常获取
- [ ] 关系按关键词筛选正常
- [ ] Chunks 列表可以正常获取
- [ ] Chunk 详情可以查看
- [ ] Chunk 关联的实体和关系正确显示
- [ ] 文档 chunks 按顺序正确排列
- [ ] 分页功能正常工作

---

## 🆘 常见问题

### Q1: 提示 "Connection refused"

**A**: 确保 LightRAG 服务器正在运行

```bash
lightrag-server
# 或
uvicorn lightrag.api.lightrag_server:app --reload --port 8020
```

### Q2: Chunks 接口返回 501 错误

**A**: 当前存储后端不支持，需要使用 JSON 存储：

```bash
# 在 .env 文件中设置
KV_STORAGE=JsonKVStorage
```

### Q3: 实体名称包含特殊字符导致 404

**A**: 需要进行 URL 编码：

```python
from urllib.parse import quote
encoded_name = quote("实体名称")
```

### Q4: 认证失败 401

**A**: 如果启用了认证，需要传递 API token：

```bash
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8020/entities/list
```

---

## 🎓 下一步

现在你已经了解了新 API 的基本用法，可以：

1. **阅读完整文档**: `docs/NewAPIEndpoints.md`
2. **查看测试代码**: `tests/test_new_api_endpoints.py`
3. **在 Swagger UI 中试验**: http://localhost:8020/docs
4. **集成到你的前端应用**

祝你使用愉快！🎉
