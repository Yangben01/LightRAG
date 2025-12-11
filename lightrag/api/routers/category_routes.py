"""
分类管理路由
提供文档分类的创建、查询、更新、删除接口
支持多租户数据隔离（通过 workspace）
"""

from typing import Optional, List, Dict, Any
import traceback
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, Query, Path, HTTPException, Request
from pydantic import BaseModel, Field

from lightrag import LightRAG
from lightrag.utils import logger
from lightrag.base import DocStatus
from ..utils_api import get_combined_auth_dependency

router = APIRouter(
    prefix="/categories",
    tags=["分类管理 / Category Management"]
)


class CategoryCreateRequest(BaseModel):
    """创建分类的请求模型"""
    name: str = Field(..., description="分类名称", min_length=1, max_length=100)
    description: Optional[str] = Field(None, description="分类描述", max_length=500)
    color: Optional[str] = Field(None, description="分类颜色（十六进制，如 #FF5733）", max_length=7)
    parent_id: Optional[str] = Field(None, description="父分类ID，用于创建子分类")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "技术文档",
                "description": "包含技术相关的文档资料",
                "color": "#3B82F6",
                "parent_id": None
            }
        }


class CategoryUpdateRequest(BaseModel):
    """更新分类的请求模型"""
    name: Optional[str] = Field(None, description="分类名称", min_length=1, max_length=100)
    description: Optional[str] = Field(None, description="分类描述", max_length=500)
    color: Optional[str] = Field(None, description="分类颜色（十六进制）", max_length=7)

    class Config:
        json_schema_extra = {
            "example": {
                "name": "技术文档（更新）",
                "description": "更新后的描述",
                "color": "#10B981"
            }
        }


class CategoryResponse(BaseModel):
    """分类响应模型"""
    id: str = Field(..., description="分类ID")
    name: str = Field(..., description="分类名称")
    description: Optional[str] = Field(None, description="分类描述")
    color: Optional[str] = Field(None, description="分类颜色")
    parent_id: Optional[str] = Field(None, description="父分类ID")
    document_count: int = Field(0, description="该分类下的文档数量")
    created_at: str = Field(..., description="创建时间（ISO格式）")
    updated_at: str = Field(..., description="更新时间（ISO格式）")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "cat_123456",
                "name": "技术文档",
                "description": "包含技术相关的文档资料",
                "color": "#3B82F6",
                "parent_id": None,
                "document_count": 15,
                "created_at": "2025-03-31T12:34:56Z",
                "updated_at": "2025-03-31T12:34:56Z"
            }
        }


class CategoryListResponse(BaseModel):
    """分类列表响应模型"""
    categories: List[CategoryResponse] = Field(..., description="分类列表")
    total: int = Field(..., description="总分类数量")

    class Config:
        json_schema_extra = {
            "example": {
                "categories": [
                    {
                        "id": "cat_123456",
                        "name": "技术文档",
                        "description": "包含技术相关的文档资料",
                        "color": "#3B82F6",
                        "parent_id": None,
                        "document_count": 15,
                        "created_at": "2025-03-31T12:34:56Z",
                        "updated_at": "2025-03-31T12:34:56Z"
                    }
                ],
                "total": 1
            }
        }


class AssignCategoryRequest(BaseModel):
    """分配分类给文档的请求模型"""
    doc_ids: List[str] = Field(..., description="文档ID列表", min_items=1)
    category_id: str = Field(..., description="分类ID")

    class Config:
        json_schema_extra = {
            "example": {
                "doc_ids": ["doc_123", "doc_456"],
                "category_id": "cat_123456"
            }
        }


class RemoveCategoryRequest(BaseModel):
    """移除文档分类的请求模型"""
    doc_ids: List[str] = Field(..., description="文档ID列表", min_items=1)

    class Config:
        json_schema_extra = {
            "example": {
                "doc_ids": ["doc_123", "doc_456"]
            }
        }


class CategoryOperationResponse(BaseModel):
    """分类操作响应模型"""
    status: str = Field(..., description="操作状态")
    message: str = Field(..., description="操作消息")
    affected_count: Optional[int] = Field(None, description="受影响的文档数量")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "message": "成功分配分类",
                "affected_count": 2
            }
        }


def format_datetime(dt: Any) -> str:
    """将datetime格式化为ISO格式字符串"""
    if isinstance(dt, str):
        return dt
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()
    return str(dt)


def doc_status_to_dict(doc_id: str, doc_status: Any) -> dict[str, Any]:
    """将DocProcessingStatus转换为字典格式用于upsert"""
    from lightrag.base import DocProcessingStatus
    return {
        "content_summary": doc_status.content_summary,
        "content_length": doc_status.content_length,
        "chunks_count": doc_status.chunks_count,
        "status": doc_status.status.value if hasattr(doc_status.status, 'value') else str(doc_status.status),
        "file_path": doc_status.file_path,
        "chunks_list": doc_status.chunks_list or [],
        "track_id": doc_status.track_id,
        "metadata": doc_status.metadata,
        "error_msg": doc_status.error_msg,
        "created_at": doc_status.created_at,
        "updated_at": doc_status.updated_at,
    }


def get_workspace_from_request(request: Request) -> str | None:
    """从请求头中提取 workspace 信息"""
    workspace = request.headers.get("LIGHTRAG-WORKSPACE", "").strip()
    return workspace if workspace else None


def get_category_storage_key(workspace: str | None, category_id: str) -> str:
    """生成分类存储的键"""
    if workspace:
        return f"{workspace}:category:{category_id}"
    return f"category:{category_id}"


def generate_category_id() -> str:
    """生成分类ID"""
    import time
    import random
    timestamp = int(time.time() * 1000)
    random_suffix = random.randint(1000, 9999)
    return f"cat_{timestamp}_{random_suffix}"


async def _get_postgres_client():
    """获取PostgreSQL数据库客户端"""
    try:
        from lightrag.kg.postgres_impl import ClientManager
        return await ClientManager.get_client()
    except Exception:
        return None


async def _is_postgres_available() -> bool:
    """检查PostgreSQL是否可用"""
    try:
        db = await _get_postgres_client()
        return db is not None
    except Exception:
        return False


async def get_category_from_storage(rag: LightRAG, workspace: str | None, category_id: str) -> Optional[Dict[str, Any]]:
    """从存储中获取分类信息"""
    try:
        workspace_name = workspace or rag.workspace or "default"
        
        # 优先使用PostgreSQL存储
        if await _is_postgres_available():
            try:
                db = await _get_postgres_client()
                sql = "SELECT id, name, description, color, parent_id, created_at, updated_at FROM LIGHTRAG_CATEGORIES WHERE workspace=$1 AND id=$2"
                result = await db.query(sql, [workspace_name, category_id], multirows=False)
                
                if result:
                    return {
                        "id": result["id"],
                        "name": result["name"],
                        "description": result.get("description"),
                        "color": result.get("color"),
                        "parent_id": result.get("parent_id"),
                        "created_at": format_datetime(result.get("created_at")),
                        "updated_at": format_datetime(result.get("updated_at")),
                    }
                return None
            except Exception as e:
                logger.warning(f"Failed to get category from PostgreSQL, falling back to JSON: {e}")
        
        # 回退到JSON文件存储
        from pathlib import Path
        from lightrag.kg.shared_storage import get_default_workspace
        
        workspace_name = workspace or get_default_workspace() or "default"
        working_dir = Path(rag.working_dir) if hasattr(rag, 'working_dir') else Path(".")
        categories_file = working_dir / "rag_storage" / workspace_name / "categories.json"
        
        if categories_file.exists():
            import json
            with open(categories_file, 'r', encoding='utf-8') as f:
                categories = json.load(f)
                return categories.get(category_id)
        
        return None
    except Exception as e:
        logger.error(f"Error getting category from storage: {e}")
        return None


async def save_category_to_storage(rag: LightRAG, workspace: str | None, category_data: Dict[str, Any]) -> bool:
    """保存分类到存储"""
    try:
        workspace_name = workspace or rag.workspace or "default"
        
        # 优先使用PostgreSQL存储
        if await _is_postgres_available():
            try:
                db = await _get_postgres_client()
                sql = """INSERT INTO LIGHTRAG_CATEGORIES (id, workspace, name, description, color, parent_id, created_at, updated_at)
                         VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                         ON CONFLICT (workspace, id) DO UPDATE SET
                         name = EXCLUDED.name,
                         description = EXCLUDED.description,
                         color = EXCLUDED.color,
                         parent_id = EXCLUDED.parent_id,
                         updated_at = EXCLUDED.updated_at"""
                
                # 解析时间字符串为datetime对象，并转换为timezone-naive格式（PostgreSQL要求）
                from datetime import datetime
                created_at = category_data.get("created_at")
                updated_at = category_data.get("updated_at")
                
                # 处理 created_at
                if isinstance(created_at, str):
                    try:
                        created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    except:
                        created_at = datetime.now(timezone.utc)
                elif created_at is None:
                    created_at = datetime.now(timezone.utc)
                
                # 处理 updated_at
                if isinstance(updated_at, str):
                    try:
                        updated_at = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                    except:
                        updated_at = datetime.now(timezone.utc)
                elif updated_at is None:
                    updated_at = datetime.now(timezone.utc)
                
                # 转换为UTC并移除时区信息（PostgreSQL存储需要timezone-naive datetime）
                if created_at.tzinfo is not None:
                    created_at = created_at.astimezone(timezone.utc).replace(tzinfo=None)
                if updated_at.tzinfo is not None:
                    updated_at = updated_at.astimezone(timezone.utc).replace(tzinfo=None)
                
                await db.execute(sql, {
                    "id": category_data['id'],
                    "workspace": workspace_name,
                    "name": category_data['name'],
                    "description": category_data.get('description'),
                    "color": category_data.get('color'),
                    "parent_id": category_data.get('parent_id'),
                    "created_at": created_at,
                    "updated_at": updated_at,
                })
                return True
            except Exception as e:
                logger.warning(f"Failed to save category to PostgreSQL, falling back to JSON: {e}")
        
        # 回退到JSON文件存储
        from pathlib import Path
        from lightrag.kg.shared_storage import get_default_workspace
        import json
        
        workspace_name = workspace or get_default_workspace() or "default"
        working_dir = Path(rag.working_dir) if hasattr(rag, 'working_dir') else Path(".")
        categories_dir = working_dir / "rag_storage" / workspace_name
        categories_dir.mkdir(parents=True, exist_ok=True)
        categories_file = categories_dir / "categories.json"
        
        # 读取现有分类
        categories = {}
        if categories_file.exists():
            with open(categories_file, 'r', encoding='utf-8') as f:
                categories = json.load(f)
        
        # 更新分类
        category_id = category_data['id']
        categories[category_id] = category_data
        
        # 保存
        with open(categories_file, 'w', encoding='utf-8') as f:
            json.dump(categories, f, ensure_ascii=False, indent=2)
        
        return True
    except Exception as e:
        logger.error(f"Error saving category to storage: {e}")
        return False


async def get_all_categories_from_storage(rag: LightRAG, workspace: str | None) -> Dict[str, Dict[str, Any]]:
    """从存储中获取所有分类"""
    try:
        workspace_name = workspace or rag.workspace or "default"
        
        # 优先使用PostgreSQL存储
        if await _is_postgres_available():
            try:
                db = await _get_postgres_client()
                sql = "SELECT id, name, description, color, parent_id, created_at, updated_at FROM LIGHTRAG_CATEGORIES WHERE workspace=$1"
                results = await db.query(sql, [workspace_name], multirows=True)
                
                if results:
                    categories = {}
                    for result in results:
                        category_id = result["id"]
                        categories[category_id] = {
                            "id": category_id,
                            "name": result["name"],
                            "description": result.get("description"),
                            "color": result.get("color"),
                            "parent_id": result.get("parent_id"),
                            "created_at": format_datetime(result.get("created_at")),
                            "updated_at": format_datetime(result.get("updated_at")),
                        }
                    return categories
                return {}
            except Exception as e:
                logger.warning(f"Failed to get categories from PostgreSQL, falling back to JSON: {e}")
        
        # 回退到JSON文件存储
        from pathlib import Path
        from lightrag.kg.shared_storage import get_default_workspace
        import json
        
        workspace_name = workspace or get_default_workspace() or "default"
        working_dir = Path(rag.working_dir) if hasattr(rag, 'working_dir') else Path(".")
        categories_file = working_dir / "rag_storage" / workspace_name / "categories.json"
        
        if categories_file.exists():
            with open(categories_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        return {}
    except Exception as e:
        logger.error(f"Error getting all categories from storage: {e}")
        return {}


async def count_documents_by_category(rag: LightRAG, workspace: str | None, category_id: str) -> int:
    """统计指定分类下的文档数量"""
    try:
        count = 0
        doc_status_storage = await get_doc_status_storage(rag, workspace)
        
        # 获取所有文档状态
        statuses = [
            DocStatus.PENDING,
            DocStatus.PROCESSING,
            DocStatus.PREPROCESSED,
            DocStatus.PROCESSED,
            DocStatus.FAILED,
        ]
        
        for status in statuses:
            docs = await doc_status_storage.get_docs_by_status(status)
            for doc_id, doc_status in docs.items():
                if doc_status.metadata and doc_status.metadata.get('category_id') == category_id:
                    count += 1
        
        return count
    except Exception as e:
        logger.error(f"Error counting documents by category: {e}")
        return 0


async def get_doc_status_storage(rag: LightRAG, workspace: str | None) -> Any:
    """获取指定工作空间的文档状态存储"""
    target_workspace = workspace or rag.workspace
    
    # 如果目标工作空间与当前rag实例一致，直接返回
    if target_workspace == rag.workspace:
        return rag.doc_status
        
    global_config = getattr(rag.doc_status, "global_config", None)
    if not global_config:
        # 尝试构建最小配置
        working_dir = getattr(rag, "working_dir", "./rag_storage")
        global_config = {"working_dir": working_dir}
        
    storage = rag.doc_status_storage_cls(
        namespace=rag.doc_status.namespace,
        workspace=target_workspace,
        global_config=global_config,
        embedding_func=None
    )
    await storage.initialize()
    return storage


def create_category_routes(rag: LightRAG, api_key: Optional[str] = None):
    """创建分类管理路由"""
    combined_auth = get_combined_auth_dependency(api_key)

    @router.post(
        "",
        response_model=CategoryResponse,
        dependencies=[Depends(combined_auth)],
        summary="创建分类",
        description="""
创建新的文档分类。

**多租户支持**：通过 `LIGHTRAG-WORKSPACE` 请求头指定工作空间。

**使用场景**：
- 为文档创建分类标签
- 组织和管理文档资料
- 支持分类层级（通过parent_id创建子分类）

**示例**：
```bash
curl -X POST "http://localhost:8020/categories" \\
  -H "LIGHTRAG-WORKSPACE: my_workspace" \\
  -H "Content-Type: application/json" \\
  -d '{
    "name": "技术文档",
    "description": "包含技术相关的文档资料",
    "color": "#3B82F6"
  }'
```
        """,
        responses={
            200: {"description": "成功创建分类"},
            400: {"description": "请求参数错误"},
            500: {"description": "服务器内部错误"}
        }
    )
    async def create_category(
        request: Request,
        category_request: CategoryCreateRequest
    ) -> CategoryResponse:
        """创建新分类"""
        try:
            workspace = get_workspace_from_request(request)
            
            # 检查分类名称是否已存在
            all_categories = await get_all_categories_from_storage(rag, workspace)
            for cat_id, cat_data in all_categories.items():
                if cat_data.get('name') == category_request.name:
                    raise HTTPException(
                        status_code=400,
                        detail=f"分类名称 '{category_request.name}' 已存在"
                    )
            
            # 如果指定了父分类，验证父分类是否存在
            if category_request.parent_id:
                parent_category = await get_category_from_storage(rag, workspace, category_request.parent_id)
                if not parent_category:
                    raise HTTPException(
                        status_code=400,
                        detail=f"父分类 '{category_request.parent_id}' 不存在"
                    )
            
            # 生成分类ID
            category_id = generate_category_id()
            
            # 创建分类数据
            now = datetime.now(timezone.utc)
            category_data = {
                "id": category_id,
                "name": category_request.name,
                "description": category_request.description,
                "color": category_request.color,
                "parent_id": category_request.parent_id,
                "created_at": format_datetime(now),
                "updated_at": format_datetime(now)
            }
            
            # 保存分类
            success = await save_category_to_storage(rag, workspace, category_data)
            if not success:
                raise HTTPException(status_code=500, detail="保存分类失败")
            
            # 统计文档数量
            document_count = await count_documents_by_category(rag, workspace, category_id)
            
            return CategoryResponse(
                id=category_id,
                name=category_data["name"],
                description=category_data["description"],
                color=category_data["color"],
                parent_id=category_data["parent_id"],
                document_count=document_count,
                created_at=category_data["created_at"],
                updated_at=category_data["updated_at"]
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error creating category: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"创建分类失败: {str(e)}")

    @router.get(
        "",
        response_model=CategoryListResponse,
        dependencies=[Depends(combined_auth)],
        summary="获取所有分类",
        description="""
获取所有文档分类列表。

**多租户支持**：通过 `LIGHTRAG-WORKSPACE` 请求头指定工作空间。

**返回内容**：
- 分类列表（包含每个分类的文档数量）
- 总分类数量

**示例**：
```bash
curl -X GET "http://localhost:8020/categories" \\
  -H "LIGHTRAG-WORKSPACE: my_workspace"
```
        """,
        responses={
            200: {"description": "成功返回分类列表"},
            500: {"description": "服务器内部错误"}
        }
    )
    async def list_categories(request: Request) -> CategoryListResponse:
        """获取所有分类"""
        try:
            workspace = get_workspace_from_request(request)
            
            # 获取所有分类
            all_categories = await get_all_categories_from_storage(rag, workspace)
            
            # 转换为响应格式并统计文档数量
            categories = []
            for cat_id, cat_data in all_categories.items():
                document_count = await count_documents_by_category(rag, workspace, cat_id)
                categories.append(CategoryResponse(
                    id=cat_data.get("id", cat_id),
                    name=cat_data.get("name", ""),
                    description=cat_data.get("description"),
                    color=cat_data.get("color"),
                    parent_id=cat_data.get("parent_id"),
                    document_count=document_count,
                    created_at=cat_data.get("created_at", format_datetime(datetime.now(timezone.utc))),
                    updated_at=cat_data.get("updated_at", format_datetime(datetime.now(timezone.utc)))
                ))
            
            return CategoryListResponse(
                categories=categories,
                total=len(categories)
            )
        except Exception as e:
            logger.error(f"Error listing categories: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"获取分类列表失败: {str(e)}")

    @router.get(
        "/{category_id}",
        response_model=CategoryResponse,
        dependencies=[Depends(combined_auth)],
        summary="获取分类详情",
        description="""
获取指定分类的详细信息。

**示例**：
```bash
curl -X GET "http://localhost:8020/categories/cat_123456" \\
  -H "LIGHTRAG-WORKSPACE: my_workspace"
```
        """,
        responses={
            200: {"description": "成功返回分类详情"},
            404: {"description": "分类不存在"},
            500: {"description": "服务器内部错误"}
        }
    )
    async def get_category(
        request: Request,
        category_id: str = Path(..., description="分类ID")
    ) -> CategoryResponse:
        """获取分类详情"""
        try:
            workspace = get_workspace_from_request(request)
            
            category_data = await get_category_from_storage(rag, workspace, category_id)
            if not category_data:
                raise HTTPException(status_code=404, detail="分类不存在")
            
            # 统计文档数量
            document_count = await count_documents_by_category(rag, workspace, category_id)
            
            return CategoryResponse(
                id=category_data.get("id", category_id),
                name=category_data.get("name", ""),
                description=category_data.get("description"),
                color=category_data.get("color"),
                parent_id=category_data.get("parent_id"),
                document_count=document_count,
                created_at=category_data.get("created_at", format_datetime(datetime.now(timezone.utc))),
                updated_at=category_data.get("updated_at", format_datetime(datetime.now(timezone.utc)))
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting category: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"获取分类详情失败: {str(e)}")

    @router.put(
        "/{category_id}",
        response_model=CategoryResponse,
        dependencies=[Depends(combined_auth)],
        summary="更新分类",
        description="""
更新指定分类的信息。

**示例**：
```bash
curl -X PUT "http://localhost:8020/categories/cat_123456" \\
  -H "LIGHTRAG-WORKSPACE: my_workspace" \\
  -H "Content-Type: application/json" \\
  -d '{
    "name": "技术文档（更新）",
    "description": "更新后的描述",
    "color": "#10B981"
  }'
```
        """,
        responses={
            200: {"description": "成功更新分类"},
            404: {"description": "分类不存在"},
            400: {"description": "请求参数错误"},
            500: {"description": "服务器内部错误"}
        }
    )
    async def update_category(
        request: Request,
        category_id: str = Path(..., description="分类ID"),
        category_request: CategoryUpdateRequest = ...
    ) -> CategoryResponse:
        """更新分类"""
        try:
            workspace = get_workspace_from_request(request)
            
            # 获取现有分类
            category_data = await get_category_from_storage(rag, workspace, category_id)
            if not category_data:
                raise HTTPException(status_code=404, detail="分类不存在")
            
            # 如果更新名称，检查是否与其他分类冲突
            if category_request.name and category_request.name != category_data.get("name"):
                all_categories = await get_all_categories_from_storage(rag, workspace)
                for cat_id, cat_data in all_categories.items():
                    if cat_id != category_id and cat_data.get('name') == category_request.name:
                        raise HTTPException(
                            status_code=400,
                            detail=f"分类名称 '{category_request.name}' 已存在"
                        )
            
            # 更新分类数据
            if category_request.name is not None:
                category_data["name"] = category_request.name
            if category_request.description is not None:
                category_data["description"] = category_request.description
            if category_request.color is not None:
                category_data["color"] = category_request.color
            
            category_data["updated_at"] = format_datetime(datetime.now(timezone.utc))
            
            # 保存更新
            success = await save_category_to_storage(rag, workspace, category_data)
            if not success:
                raise HTTPException(status_code=500, detail="更新分类失败")
            
            # 统计文档数量
            document_count = await count_documents_by_category(rag, workspace, category_id)
            
            return CategoryResponse(
                id=category_data.get("id", category_id),
                name=category_data.get("name", ""),
                description=category_data.get("description"),
                color=category_data.get("color"),
                parent_id=category_data.get("parent_id"),
                document_count=document_count,
                created_at=category_data.get("created_at", format_datetime(datetime.now(timezone.utc))),
                updated_at=category_data.get("updated_at")
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error updating category: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"更新分类失败: {str(e)}")

    @router.delete(
        "/{category_id}",
        response_model=CategoryOperationResponse,
        dependencies=[Depends(combined_auth)],
        summary="删除分类",
        description="""
删除指定分类。注意：删除分类不会删除该分类下的文档，只会移除文档的分类标签。

**示例**：
```bash
curl -X DELETE "http://localhost:8020/categories/cat_123456" \\
  -H "LIGHTRAG-WORKSPACE: my_workspace"
```
        """,
        responses={
            200: {"description": "成功删除分类"},
            404: {"description": "分类不存在"},
            500: {"description": "服务器内部错误"}
        }
    )
    async def delete_category(
        request: Request,
        category_id: str = Path(..., description="分类ID")
    ) -> CategoryOperationResponse:
        """删除分类"""
        try:
            workspace = get_workspace_from_request(request)
            
            # 检查分类是否存在
            category_data = await get_category_from_storage(rag, workspace, category_id)
            if not category_data:
                raise HTTPException(status_code=404, detail="分类不存在")
            
            # 检查是否有子分类
            all_categories = await get_all_categories_from_storage(rag, workspace)
            has_children = any(
                cat_data.get("parent_id") == category_id
                for cat_data in all_categories.values()
            )
            if has_children:
                raise HTTPException(
                    status_code=400,
                    detail="无法删除分类：该分类下存在子分类，请先删除子分类"
                )
            
            workspace_name = workspace or rag.workspace or "default"
            
            # 统计受影响的文档数量
            affected_count = await count_documents_by_category(rag, workspace, category_id)
            
            doc_status_storage = await get_doc_status_storage(rag, workspace)
            
            # 移除所有文档的该分类标签
            if affected_count > 0:
                statuses = [
                    DocStatus.PENDING,
                    DocStatus.PROCESSING,
                    DocStatus.PREPROCESSED,
                    DocStatus.PROCESSED,
                    DocStatus.FAILED,
                ]
                
                docs_to_update = {}
                for status in statuses:
                    docs = await doc_status_storage.get_docs_by_status(status)
                    for doc_id, doc_status in docs.items():
                        if doc_status.metadata and doc_status.metadata.get('category_id') == category_id:
                            # 更新文档metadata，移除分类
                            if not doc_status.metadata:
                                doc_status.metadata = {}
                            doc_status.metadata.pop('category_id', None)
                            docs_to_update[doc_id] = doc_status
                
                # 批量保存更新
                if docs_to_update:
                    docs_dict = {doc_id: doc_status_to_dict(doc_id, doc_status) for doc_id, doc_status in docs_to_update.items()}
                    await doc_status_storage.upsert(docs_dict)
            
            # 从存储中删除分类
            # 优先使用PostgreSQL存储
            if await _is_postgres_available():
                try:
                    db = await _get_postgres_client()
                    sql = "DELETE FROM LIGHTRAG_CATEGORIES WHERE workspace=$1 AND id=$2"
                    await db.execute(sql, {"workspace": workspace_name, "id": category_id})
                except Exception as e:
                    logger.warning(f"Failed to delete category from PostgreSQL, falling back to JSON: {e}")
                    # 回退到JSON文件存储
                    all_categories.pop(category_id, None)
                    from pathlib import Path
                    from lightrag.kg.shared_storage import get_default_workspace
                    import json
                    
                    workspace_name = workspace or get_default_workspace() or "default"
                    working_dir = Path(rag.working_dir) if hasattr(rag, 'working_dir') else Path(".")
                    categories_file = working_dir / "rag_storage" / workspace_name / "categories.json"
                    
                    if categories_file.exists():
                        with open(categories_file, 'w', encoding='utf-8') as f:
                            json.dump(all_categories, f, ensure_ascii=False, indent=2)
            else:
                # 使用JSON文件存储
                all_categories.pop(category_id, None)
                from pathlib import Path
                from lightrag.kg.shared_storage import get_default_workspace
                import json
                
                workspace_name = workspace or get_default_workspace() or "default"
                working_dir = Path(rag.working_dir) if hasattr(rag, 'working_dir') else Path(".")
                categories_file = working_dir / "rag_storage" / workspace_name / "categories.json"
                
                if categories_file.exists():
                    with open(categories_file, 'w', encoding='utf-8') as f:
                        json.dump(all_categories, f, ensure_ascii=False, indent=2)
            
            return CategoryOperationResponse(
                status="success",
                message="分类已删除",
                affected_count=affected_count
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error deleting category: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"删除分类失败: {str(e)}")

    @router.post(
        "/assign",
        response_model=CategoryOperationResponse,
        dependencies=[Depends(combined_auth)],
        summary="为文档分配分类",
        description="""
为指定的文档分配分类标签。

**示例**：
```bash
curl -X POST "http://localhost:8020/categories/assign" \\
  -H "LIGHTRAG-WORKSPACE: my_workspace" \\
  -H "Content-Type: application/json" \\
  -d '{
    "doc_ids": ["doc_123", "doc_456"],
    "category_id": "cat_123456"
  }'
```
        """,
        responses={
            200: {"description": "成功分配分类"},
            400: {"description": "请求参数错误"},
            404: {"description": "分类不存在"},
            500: {"description": "服务器内部错误"}
        }
    )
    async def assign_category(
        request: Request,
        assign_request: AssignCategoryRequest
    ) -> CategoryOperationResponse:
        """为文档分配分类"""
        try:
            workspace = get_workspace_from_request(request)
            
            # 验证分类是否存在
            category_data = await get_category_from_storage(rag, workspace, assign_request.category_id)
            if not category_data:
                raise HTTPException(status_code=404, detail="分类不存在")
            
            doc_status_storage = await get_doc_status_storage(rag, workspace)
            
            # 更新文档的metadata
            affected_count = 0
            statuses = [
                DocStatus.PENDING,
                DocStatus.PROCESSING,
                DocStatus.PREPROCESSED,
                DocStatus.PROCESSED,
                DocStatus.FAILED,
            ]
            
            docs_to_update = {}
            for status in statuses:
                docs = await doc_status_storage.get_docs_by_status(status)
                for doc_id in assign_request.doc_ids:
                    if doc_id in docs:
                        doc_status = docs[doc_id]
                        if not doc_status.metadata:
                            doc_status.metadata = {}
                        doc_status.metadata['category_id'] = assign_request.category_id
                        docs_to_update[doc_id] = doc_status
                        affected_count += 1
            
            # 批量保存更新
            if docs_to_update:
                # 需要将DocProcessingStatus转换为字典格式
                docs_dict = {doc_id: doc_status_to_dict(doc_id, doc_status) for doc_id, doc_status in docs_to_update.items()}
                await doc_status_storage.upsert(docs_dict)
            
            if affected_count == 0:
                raise HTTPException(
                    status_code=400,
                    detail="未找到指定的文档"
                )
            
            return CategoryOperationResponse(
                status="success",
                message=f"成功为 {affected_count} 个文档分配分类",
                affected_count=affected_count
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error assigning category: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"分配分类失败: {str(e)}")

    @router.post(
        "/remove",
        response_model=CategoryOperationResponse,
        dependencies=[Depends(combined_auth)],
        summary="移除文档的分类",
        description="""
移除指定文档的分类标签。

**示例**：
```bash
curl -X POST "http://localhost:8020/categories/remove" \\
  -H "LIGHTRAG-WORKSPACE: my_workspace" \\
  -H "Content-Type: application/json" \\
  -d '{
    "doc_ids": ["doc_123", "doc_456"]
  }'
```
        """,
        responses={
            200: {"description": "成功移除分类"},
            500: {"description": "服务器内部错误"}
        }
    )
    async def remove_category(
        request: Request,
        remove_request: RemoveCategoryRequest
    ) -> CategoryOperationResponse:
        """移除文档的分类"""
        try:
            workspace = get_workspace_from_request(request)
            doc_status_storage = await get_doc_status_storage(rag, workspace)
            
            # 更新文档的metadata
            affected_count = 0
            statuses = [
                DocStatus.PENDING,
                DocStatus.PROCESSING,
                DocStatus.PREPROCESSED,
                DocStatus.PROCESSED,
                DocStatus.FAILED,
            ]
            
            docs_to_update = {}
            for status in statuses:
                docs = await doc_status_storage.get_docs_by_status(status)
                for doc_id in remove_request.doc_ids:
                    if doc_id in docs:
                        doc_status = docs[doc_id]
                        if doc_status.metadata and doc_status.metadata.get('category_id'):
                            doc_status.metadata.pop('category_id', None)
                            docs_to_update[doc_id] = doc_status
                            affected_count += 1
            
            # 批量保存更新
            if docs_to_update:
                # 需要将DocProcessingStatus转换为字典格式
                docs_dict = {doc_id: doc_status_to_dict(doc_id, doc_status) for doc_id, doc_status in docs_to_update.items()}
                await doc_status_storage.upsert(docs_dict)
            
            return CategoryOperationResponse(
                status="success",
                message=f"成功移除 {affected_count} 个文档的分类",
                affected_count=affected_count
            )
        except Exception as e:
            logger.error(f"Error removing category: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"移除分类失败: {str(e)}")

    return router

