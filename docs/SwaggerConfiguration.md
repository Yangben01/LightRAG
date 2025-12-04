# LightRAG Swagger API 文档配置说明

## 📋 概述

LightRAG API 已完整集成 Swagger/OpenAPI 文档，提供交互式 API 测试界面和完善的接口说明。

## 🎯 访问 API 文档

启动 LightRAG 服务器后，可通过以下方式访问 API 文档：

### 1. Swagger UI (推荐)
```
http://localhost:8020/docs
```

**特性**：
- ✅ 交互式 API 测试
- ✅ 自动保存认证信息 (`persistAuthorization`)
- ✅ 显示请求耗时
- ✅ 可过滤和搜索接口
- ✅ 离线支持（本地静态资源）

### 2. ReDoc
```
http://localhost:8020/redoc
```

**特性**：
- ✅ 更友好的阅读体验
- ✅ 三栏布局（导航、内容、示例）
- ✅ 更好的响应模型展示

### 3. OpenAPI Schema
```
http://localhost:8020/openapi.json
```

用于导入到其他 API 工具（如 Postman、Insomnia）。

## 📚 API 模块分类

### 🗂️ 文档管理 (Document Management)
**路由前缀**: `/documents`

主要接口：
- `POST /documents/upload` - 上传文档
- `POST /documents/scan` - 扫描目录
- `POST /documents/text` - 插入单个文本
- `POST /documents/texts` - 批量插入文本
- `DELETE /documents` - 清空所有文档
- `DELETE /documents/delete_document` - 删除指定文档
- `GET /documents/pipeline_status` - 获取处理状态
- `GET /documents/track_status/{track_id}` - 追踪处理进度
- `POST /documents/paginated` - 分页查询文档
- `POST /documents/reprocess_failed` - 重新处理失败文档
- `POST /documents/cancel_pipeline` - 取消处理任务

**Tag**: `documents`

### 🔍 知识检索 (Query Routes)
**路由前缀**: `/query`

主要接口：
- `POST /query` - 标准查询
- `POST /query/stream` - 流式查询
- `POST /query/data` - 结构化数据查询

**Tag**: `query`

### 🕸️ 知识图谱 (Graph Routes)
**路由前缀**: `/graph`

主要接口：
- `GET /graphs` - 获取知识图谱数据
- `GET /graph/label/list` - 获取所有标签
- `POST /graph/entity/create` - 创建实体
- `POST /graph/entity/update` - 更新实体
- `POST /graph/relation/create` - 创建关系
- `POST /graph/relation/edit` - 编辑关系

**Tag**: `graph`

### 👥 实体管理 (Entity Management)
**路由**: `/entities/*`

主要接口：
- `GET /entities/list` - 获取实体列表（分页、筛选）
- `GET /entities/{entity_name}` - 获取实体详情
- `GET /entities/{entity_name}/relations` - 获取实体的所有关系

**Tag**: `实体和关系管理 / Entity & Relation Management`

### 🔗 关系管理 (Relation Management)
**路由**: `/relations/*`

主要接口：
- `GET /relations/list` - 获取关系列表（分页、筛选）

**Tag**: `实体和关系管理 / Entity & Relation Management`

### 📄 文档分块 (Chunk Management)
**路由**: `/chunks/*`, `/documents/{doc_id}/chunks`

主要接口：
- `GET /chunks/list` - 获取chunk列表
- `GET /chunks/{chunk_id}` - 获取chunk详情
- `GET /documents/{doc_id}/chunks` - 获取文档的所有chunks

**Tag**: `文档分块管理 / Chunk Management`

### 🤖 Ollama 兼容 API
**路由前缀**: `/api` (兼容 Ollama API)

主要接口：
- `GET /api/tags` - 获取模型列表
- `POST /api/chat` - 聊天接口
- `POST /api/embeddings` - 向量接口

**Tag**: `ollama`

## 🔐 认证配置

### API Key 认证

如果启用了 API Key（通过 `.env` 文件的 `LIGHTRAG_API_KEY`），在 Swagger UI 中：

1. 点击右上角的 **"Authorize"** 按钮
2. 在弹出框中输入 API Key
3. 点击 **"Authorize"**
4. 认证信息会自动保存（`persistAuthorization` 特性）

**Header 格式**:
```
Authorization: Bearer YOUR_API_KEY
```

### 无认证模式

如果未配置 API Key，所有接口可直接访问，无需认证。

## 🏢 多租户支持

所有新开发的 API（实体、关系、分块）都支持多租户数据隔离。

### 使用方法

在请求头中添加 `LIGHTRAG-WORKSPACE` 指定工作空间：

**示例**：
```bash
# 租户A的请求
curl -X GET "http://localhost:8020/entities/list" \
  -H "LIGHTRAG-WORKSPACE: tenant_a" \
  -H "Authorization: Bearer YOUR_API_KEY"

# 租户B的请求
curl -X GET "http://localhost:8020/entities/list" \
  -H "LIGHTRAG-WORKSPACE: tenant_b" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### 在 Swagger UI 中使用

对于支持多租户的接口，在 Swagger UI 的 **"Try it out"** 模式中：

1. 找到 **"LIGHTRAG-WORKSPACE"** 参数（如果接口支持）
2. 或者手动在 Headers 中添加：
   ```
   LIGHTRAG-WORKSPACE: your_workspace_name
   ```

**注意**：如果不指定 workspace，将使用服务器的默认 workspace。

## 🎨 Swagger UI 配置

LightRAG 的 Swagger UI 已配置以下特性：

### 持久化认证 (`persistAuthorization`)
- 认证信息保存在浏览器 localStorage
- 刷新页面后无需重新登录

### 显示请求耗时 (`displayRequestDuration`)
- 显示每个 API 请求的响应时间
- 帮助评估性能

### 过滤功能 (`filter`)
- 在 Swagger UI 顶部有搜索框
- 可按接口路径、标签或描述过滤

### 默认折叠 (`docExpansion: "none"`)
- 初始加载时所有接口都是折叠状态
- 点击展开查看详情

### Try It Out 默认启用 (`tryItOutEnabled`)
- 每个接口默认开启测试模式
- 可直接填写参数并发送请求

## 📝 API 示例

### 获取实体列表
```bash
curl -X GET "http://localhost:8020/entities/list?page=1&page_size=20&entity_type=PERSON" \
  -H "LIGHTRAG-WORKSPACE: my_workspace" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### 获取实体详情
```bash
curl -X GET "http://localhost:8020/entities/特斯拉" \
  -H "LIGHTRAG-WORKSPACE: my_workspace" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### 获取关系列表
```bash
curl -X GET "http://localhost:8020/relations/list?entity_name=特斯拉" \
  -H "LIGHTRAG-WORKSPACE: my_workspace" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### 获取文档分块
```bash
curl -X GET "http://localhost:8020/chunks/list?page=1&page_size=20" \
  -H "LIGHTRAG-WORKSPACE: my_workspace" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### 获取文档的所有chunks
```bash
curl -X GET "http://localhost:8020/documents/doc-123/chunks" \
  -H "LIGHTRAG-WORKSPACE: my_workspace" \
  -H "Authorization: Bearer YOUR_API_KEY"
```

## 🛠️ 开发建议

### 1. 使用 Swagger UI 测试
在开发和调试阶段，推荐使用 Swagger UI 进行 API 测试：
- 自动生成请求示例
- 实时查看响应数据
- 自动处理认证

### 2. 导出 OpenAPI Schema
```bash
curl http://localhost:8020/openapi.json > lightrag-openapi.json
```

然后可以导入到：
- **Postman**: File → Import → OpenAPI 3.0
- **Insomnia**: Create → Import/Export → Import Data
- **API Client 生成器**: 使用 openapi-generator 生成各语言客户端

### 3. 查看 ReDoc
需要更友好的阅读体验时访问 `/redoc`：
- 更清晰的结构
- 更好的代码示例
- 更易于导航

## 📊 响应格式

### 成功响应
```json
{
  "status": "success",
  "data": { ... },
  "message": "操作成功"
}
```

### 错误响应
```json
{
  "detail": "错误详情"
}
```

### 分页响应
```json
{
  "total": 100,
  "page": 1,
  "page_size": 20,
  "items": [ ... ]
}
```

## 🔧 自定义配置

### 修改 Swagger UI 参数

编辑 `lightrag/api/lightrag_server.py`：

```python
app_kwargs["swagger_ui_parameters"] = {
    "persistAuthorization": True,
    "tryItOutEnabled": True,
    "displayRequestDuration": True,
    "filter": True,
    "showExtensions": True,
    "docExpansion": "none",  # 可选: "list", "full", "none"
    "defaultModelsExpandDepth": 1,
    "defaultModelExpandDepth": 1,
}
```

### 添加自定义描述

在路由装饰器中添加详细的 `description` 和 `responses`：

```python
@router.get(
    "/your-endpoint",
    summary="简短标题",
    description="""
详细的多行描述
支持 Markdown 格式
    """,
    responses={
        200: {
            "description": "成功响应",
            "content": {
                "application/json": {
                    "example": {"key": "value"}
                }
            }
        },
        404: {"description": "资源不存在"}
    }
)
```

## 📖 相关文档

- [新 API 端点文档](./NewAPIEndpoints.md)
- [新 API 端点文档（中文）](./NewAPIEndpoints-zh.md)
- [快速开始指南](./QuickStart-NewAPIs.md)
- [多租户支持](./MultiTenantSupport.md)
- [离线部署](./OfflineDeployment.md)

## 🎉 总结

LightRAG 的 Swagger 配置提供了：

✅ **完整的 API 文档** - 所有接口都有详细说明  
✅ **交互式测试** - 直接在浏览器中测试 API  
✅ **多租户支持** - 通过 workspace 实现数据隔离  
✅ **认证集成** - 支持 API Key 认证  
✅ **离线支持** - 本地静态资源，无需外网  
✅ **丰富示例** - 每个接口都有请求/响应示例  
✅ **用户友好** - 持久化认证、过滤、搜索等特性  

开始使用：访问 http://localhost:8020/docs 🚀

