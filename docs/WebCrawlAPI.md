# 网页抓取API接口文档

## 接口信息

- **路径**: `/documents/crawl`
- **方法**: `POST`
- **认证**: 需要API Key或Bearer Token（根据配置）
- **Content-Type**: `application/json`

## 请求参数

### 参数说明

| 参数名 | 类型 | 必填 | 默认值 | 说明 |
|--------|------|------|--------|------|
| `url` | string | ✅ | - | 要抓取的网页URL，必须以 `http://` 或 `https://` 开头 |
| `title` | string | ❌ | null | 可选的网页标题。如果不提供，系统会从网页的 `<title>` 或 `<h1>` 标签中自动提取 |
| `crawl_links` | boolean | ❌ | false | 是否自动抓取页面中的相关链接。启用后会从页面中提取链接并批量抓取 |
| `max_links` | integer | ❌ | 10 | 最大抓取链接数量（仅在 `crawl_links=true` 时有效）。范围：1-100 |
| `same_domain_only` | boolean | ❌ | true | 是否只抓取同域名的链接（仅在 `crawl_links=true` 时有效）。设置为 `false` 时会抓取所有外部链接 |
| `link_pattern` | string | ❌ | null | 链接路径模式过滤（仅在 `crawl_links=true` 时有效）。例如：`.asp` 表示只抓取包含 `.asp` 的链接，`/products/` 表示只抓取包含 `/products/` 路径的链接 |

### 参数约束

- `url`: 必须非空，且以 `http://` 或 `https://` 开头
- `max_links`: 必须在 1-100 之间
- `link_pattern`: 如果提供，会作为子字符串匹配链接路径

## 请求示例

### 1. 基础示例 - 单页面抓取

#### cURL

```bash
curl -X POST "http://localhost:9621/documents/crawl" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "url": "http://www.chujugo.cn/case.asp"
  }'
```

#### Python (requests)

```python
import requests

url = "http://localhost:9621/documents/crawl"
headers = {
    "Content-Type": "application/json",
    "X-API-Key": "your-api-key"
}
data = {
    "url": "http://www.chujugo.cn/case.asp"
}

response = requests.post(url, json=data, headers=headers)
print(response.json())
```

#### Python (httpx - 异步)

```python
import httpx

async def crawl_page():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:9621/documents/crawl",
            json={
                "url": "http://www.chujugo.cn/case.asp"
            },
            headers={
                "X-API-Key": "your-api-key"
            }
        )
        return response.json()
```

#### JavaScript (fetch)

```javascript
fetch('http://localhost:9621/documents/crawl', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-API-Key': 'your-api-key'
  },
  body: JSON.stringify({
    url: 'http://www.chujugo.cn/case.asp'
  })
})
.then(response => response.json())
.then(data => console.log(data));
```

### 2. 带标题的单页面抓取

```bash
curl -X POST "http://localhost:9621/documents/crawl" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "url": "http://www.chujugo.cn/case.asp",
    "title": "成功案例页面"
  }'
```

### 3. 批量抓取 - 抓取相关链接

```bash
curl -X POST "http://localhost:9621/documents/crawl" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "url": "http://www.chujugo.cn/case.asp",
    "crawl_links": true,
    "max_links": 10,
    "same_domain_only": true,
    "link_pattern": ".asp"
  }'
```

### 4. 批量抓取 - 抓取所有同域名链接

```bash
curl -X POST "http://localhost:9621/documents/crawl" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "url": "https://example.com/index.html",
    "crawl_links": true,
    "max_links": 20,
    "same_domain_only": true
  }'
```

### 5. 批量抓取 - 包含外部链接

```bash
curl -X POST "http://localhost:9621/documents/crawl" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "url": "https://example.com/article",
    "crawl_links": true,
    "max_links": 15,
    "same_domain_only": false,
    "link_pattern": "/blog/"
  }'
```

## 响应示例

### 成功响应

```json
{
  "status": "success",
  "message": "成功抓取 5 个页面（主页面 + 4 个相关链接）。将在后台继续处理。",
  "track_id": "crawl_20250123_143022_abc123"
}
```

### 重复内容响应

```json
{
  "status": "duplicated",
  "message": "网页 'http://www.chujugo.cn/case.asp' 已存在于文档存储中（状态: processed）。",
  "track_id": "upload_20250120_100000_xyz789"
}
```

### 错误响应

```json
{
  "detail": "无法访问网页: HTTP 404"
}
```

## 响应字段说明

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `status` | string | 操作状态。可能的值：`success`（成功）、`duplicated`（已存在） |
| `message` | string | 操作结果的详细描述信息 |
| `track_id` | string | 跟踪ID，用于查询文档处理进度。格式：`crawl_YYYYMMDD_HHMMSS_随机字符串` |

## 使用场景示例

### 场景1: 抓取单个新闻文章

```json
{
  "url": "https://news.example.com/article/12345",
  "title": "重要新闻标题"
}
```

### 场景2: 抓取网站的所有产品页面

```json
{
  "url": "https://shop.example.com/products",
  "crawl_links": true,
  "max_links": 50,
  "same_domain_only": true,
  "link_pattern": "/products/"
}
```

### 场景3: 抓取博客的所有文章

```json
{
  "url": "https://blog.example.com",
  "crawl_links": true,
  "max_links": 30,
  "same_domain_only": true,
  "link_pattern": "/posts/"
}
```

### 场景4: 抓取ASP网站的所有页面

```json
{
  "url": "http://www.chujugo.cn/index.asp",
  "crawl_links": true,
  "max_links": 20,
  "same_domain_only": true,
  "link_pattern": ".asp"
}
```

## 注意事项

1. **异步处理**: 接口会立即返回，实际的知识提取和处理在后台进行。使用返回的 `track_id` 可以通过 `/track_status/{track_id}` 接口查询处理进度。

2. **去重机制**: 
   - 系统会检查URL是否已存在
   - 系统会检查内容是否重复（基于内容哈希）
   - 已存在的页面会被跳过

3. **批量抓取限制**:
   - `max_links` 最大值为 100
   - 实际抓取数量 = 主页面 + 最多 `max_links` 个相关链接
   - 如果链接数量超过限制，会按提取顺序抓取前 `max_links` 个

4. **链接过滤规则**:
   - 自动过滤：`#` 锚点、`javascript:` 链接、`mailto:` 链接
   - 如果 `same_domain_only=true`，只抓取同域名的链接
   - 如果提供 `link_pattern`，只抓取路径中包含该模式的链接

5. **处理时间**: 
   - 单页面抓取通常几秒内完成
   - 批量抓取时间取决于链接数量和页面大小
   - 知识提取和处理在后台异步进行，可能需要更长时间

## 查询处理进度

抓取请求返回后，可以使用 `track_id` 查询处理进度：

```bash
curl "http://localhost:9621/track_status/crawl_20250123_143022_abc123" \
  -H "X-API-Key: your-api-key"
```

响应示例：

```json
{
  "status": "processing",
  "message": "正在处理文档...",
  "progress": 0.5,
  "total_documents": 5,
  "processed_documents": 2
}
```

## 错误码说明

| HTTP状态码 | 说明 |
|-----------|------|
| 200 | 请求成功 |
| 400 | 请求参数错误（如URL格式不正确、无法访问网页等） |
| 401 | 未授权（API Key或Token无效） |
| 500 | 服务器内部错误 |

## 完整示例代码

### Python完整示例

```python
import requests
import time

def crawl_website(base_url, max_pages=10, link_pattern=None):
    """
    抓取网站并监控处理进度
    """
    api_url = "http://localhost:9621/documents/crawl"
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": "your-api-key"
    }
    
    # 构建请求数据
    data = {
        "url": base_url,
        "crawl_links": True,
        "max_links": max_pages,
        "same_domain_only": True
    }
    
    if link_pattern:
        data["link_pattern"] = link_pattern
    
    # 发送抓取请求
    response = requests.post(api_url, json=data, headers=headers)
    result = response.json()
    
    if result.get("status") == "success":
        track_id = result.get("track_id")
        print(f"抓取请求已提交，track_id: {track_id}")
        
        # 查询处理进度
        while True:
            status_response = requests.get(
                f"http://localhost:9621/track_status/{track_id}",
                headers=headers
            )
            status = status_response.json()
            
            print(f"处理状态: {status.get('status')} - {status.get('message')}")
            
            if status.get("status") in ["processed", "failed"]:
                break
            
            time.sleep(2)  # 每2秒查询一次
        
        return status
    else:
        print(f"抓取失败: {result.get('message')}")
        return result

# 使用示例
if __name__ == "__main__":
    result = crawl_website(
        base_url="http://www.chujugo.cn/case.asp",
        max_pages=10,
        link_pattern=".asp"
    )
    print(result)
```

