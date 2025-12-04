# LightRAG Swagger API 配置说明

## ✨ 主要特性

LightRAG API 已完整集成 Swagger 文档，提供：

- 🎯 **交互式 API 测试界面**
- 📚 **完整的接口文档和示例**
- 🏢 **多租户数据隔离支持**
- 🔐 **API Key 认证集成**
- 🌐 **离线支持**（本地静态资源）

## 🚀 快速开始

### 访问 Swagger UI

```
http://localhost:8020/docs
```

### 访问 ReDoc（更友好的阅读界面）

```
http://localhost:8020/redoc
```

### 获取 OpenAPI Schema（用于导入 Postman 等工具）

```
http://localhost:8020/openapi.json
```

## 📋 API 模块分类

| 模块           | 路由前缀     | Tag              | 说明                               |
| -------------- | ------------ | ---------------- | ---------------------------------- |
| **文档管理**   | `/documents` | `documents`      | 上传、扫描、删除文档，追踪处理状态 |
| **知识检索**   | `/query`     | `query`          | 标准查询、流式查询、数据查询       |
| **知识图谱**   | `/graph`     | `graph`          | 图谱数据、标签管理                 |
| **实体管理**   | `/entities`  | `实体和关系管理` | 列表、详情、筛选、搜索             |
| **关系管理**   | `/relations` | `实体和关系管理` | 关系列表、筛选                     |
| **文档分块**   | `/chunks`    | `文档分块管理`   | Chunk 列表、详情、关联信息         |
| **Ollama API** | `/api`       | `ollama`         | Ollama 兼容接口                    |

## 🏢 多租户使用

所有新开发的 API 都支持通过 `LIGHTRAG-WORKSPACE` 请求头实现数据隔离：

```bash
# 租户A
curl -H "LIGHTRAG-WORKSPACE: tenant_a" http://localhost:8020/entities/list

# 租户B
curl -H "LIGHTRAG-WORKSPACE: tenant_b" http://localhost:8020/entities/list
```

**在 Swagger UI 中使用**：

1. 点击 "Try it out"
2. 在 Headers 中添加：`LIGHTRAG-WORKSPACE: your_workspace_name`
3. 执行请求

## 🔐 API Key 认证

如果启用了 API Key：

1. 点击 Swagger UI 右上角的 **"Authorize"** 按钮
2. 输入 API Key
3. 点击 **"Authorize"**
4. 认证信息会自动保存（刷新页面后无需重新输入）

## 🎨 Swagger UI 特性

✅ **持久化认证** - 刷新页面无需重新登录  
✅ **显示请求耗时** - 评估 API 性能  
✅ **过滤搜索** - 快速找到需要的接口  
✅ **默认测试模式** - 直接测试 API  
✅ **自动补全** - 智能提示参数

## 📝 常用示例

### 获取实体列表（分页 + 类型筛选）

```bash
curl -X GET "http://localhost:8020/entities/list?page=1&page_size=20&entity_type=PERSON" \
  -H "LIGHTRAG-WORKSPACE: my_workspace"
```

### 获取实体详情

```bash
curl -X GET "http://localhost:8020/entities/特斯拉" \
  -H "LIGHTRAG-WORKSPACE: my_workspace"
```

### 获取关系列表（按实体筛选）

```bash
curl -X GET "http://localhost:8020/relations/list?entity_name=特斯拉" \
  -H "LIGHTRAG-WORKSPACE: my_workspace"
```

### 获取文档分块

```bash
curl -X GET "http://localhost:8020/chunks/list?page=1&page_size=20" \
  -H "LIGHTRAG-WORKSPACE: my_workspace"
```

### 获取文档的所有 chunks

```bash
curl -X GET "http://localhost:8020/documents/doc-123/chunks" \
  -H "LIGHTRAG-WORKSPACE: my_workspace"
```

## 🛠️ 导出和集成

### 导出 OpenAPI Schema

```bash
curl http://localhost:8020/openapi.json > lightrag-openapi.json
```

### 导入到其他工具

- **Postman**: File → Import → OpenAPI 3.0
- **Insomnia**: Create → Import/Export → Import Data
- **代码生成**: 使用 openapi-generator 生成各语言客户端

## 📖 详细文档

- [完整 Swagger 配置说明](./SwaggerConfiguration.md)
- [新 API 端点文档](./NewAPIEndpoints-zh.md)
- [快速开始指南](./QuickStart-NewAPIs.md)
- [多租户支持文档](./MultiTenantSupport.md)

## 🎉 开始使用

访问 http://localhost:8020/docs 立即体验交互式 API 文档！🚀
