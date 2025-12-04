"""
文档分块(Chunk)管理路由
提供文档chunks的查询接口
支持多租户数据隔离（通过 workspace）
"""

from typing import Optional, List, Dict, Any
import traceback
from fastapi import APIRouter, Depends, Query, HTTPException, Request
from pydantic import BaseModel, Field

from lightrag.utils import logger
from ..utils_api import get_combined_auth_dependency

router = APIRouter(
    tags=["文档分块管理 / Chunk Management"]
)


class ChunkListResponse(BaseModel):
    """Chunk列表响应"""

    total: int = Field(..., description="总chunk数量")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")
    chunks: List[Dict[str, Any]] = Field(..., description="Chunk列表")


def create_chunk_routes(rag, api_key: Optional[str] = None):
    """创建chunk管理路由"""
    combined_auth = get_combined_auth_dependency(api_key)

    @router.get(
        "/chunks/list",
        dependencies=[Depends(combined_auth)],
        response_model=ChunkListResponse,
        summary="获取文档分块列表",
        description="""
获取所有文档分块(chunk)，支持分页和按文档ID筛选。

**多租户支持**：通过 `LIGHTRAG-WORKSPACE` 请求头指定工作空间。

**什么是 Chunk？**
Chunk 是文档被切分后的片段，每个 chunk 包含：
- 原始文本内容
- Token 数量
- 所属文档ID
- 顺序索引

**使用场景**：
- 查看文档的分块情况
- 检查特定文档的所有分块
- 分析文本分块策略

**示例**：
```bash
# 获取所有chunks
curl -X GET "http://localhost:8020/chunks/list?page=1&page_size=20" \\
  -H "LIGHTRAG-WORKSPACE: my_workspace"

# 获取特定文档的chunks
curl -X GET "http://localhost:8020/chunks/list?doc_id=doc-123" \\
  -H "LIGHTRAG-WORKSPACE: my_workspace"
```

**注意**：目前仅支持 JSON 存储后端。
        """,
        responses={
            200: {
                "description": "成功返回chunk列表",
                "content": {
                    "application/json": {
                        "example": {
                            "total": 100,
                            "page": 1,
                            "page_size": 20,
                            "chunks": [
                                {
                                    "chunk_id": "chunk-abc123",
                                    "content": "这是文档的第一段内容...",
                                    "tokens": 150,
                                    "full_doc_id": "doc-xyz789",
                                    "chunk_order_index": 0
                                }
                            ]
                        }
                    }
                }
            },
            501: {"description": "当前存储后端不支持此操作"},
            500: {"description": "服务器内部错误"}
        },
        tags=["文档分块管理 / Chunk Management"]
    )
    async def list_chunks(
        request: Request,
        page: int = Query(1, ge=1, description="页码，从1开始"),
        page_size: int = Query(50, ge=1, le=500, description="每页数量，最大500"),
        doc_id: Optional[str] = Query(None, description="按文档ID筛选"),
    ):
        """
        获取chunk列表，支持分页

        参数:
        - page: 页码 (从1开始)
        - page_size: 每页数量 (1-500)
        - doc_id: 按文档ID筛选 (可选)

        返回:
        - total: 总chunk数量
        - page: 当前页码
        - page_size: 每页数量
        - chunks: chunk列表，每个chunk包含:
            - chunk_id: chunk ID
            - content: chunk内容
            - tokens: token数量
            - full_doc_id: 所属文档ID
            - chunk_order_index: chunk顺序索引
        """
        try:
            # 从text_chunks存储中获取所有chunks
            # text_chunks是BaseKVStorage，我们需要获取所有数据
            # 由于BaseKVStorage没有get_all方法，我们需要使用内部存储方法

            # 对于JSON存储，可以直接访问内部数据
            if hasattr(rag.text_chunks, "_data"):
                all_chunks_dict = rag.text_chunks._data
            else:
                # 如果没有_data属性，抛出错误
                raise HTTPException(
                    status_code=501,
                    detail="当前存储后端不支持列出所有chunks，请使用JSON存储",
                )

            # 转换为列表
            all_chunks = []
            for chunk_id, chunk_data in all_chunks_dict.items():
                chunk_info = {
                    "chunk_id": chunk_id,
                    "content": chunk_data.get("content", ""),
                    "tokens": chunk_data.get("tokens", 0),
                    "full_doc_id": chunk_data.get("full_doc_id", ""),
                    "chunk_order_index": chunk_data.get("chunk_order_index", 0),
                }
                all_chunks.append(chunk_info)

            # 按文档ID筛选
            if doc_id:
                all_chunks = [
                    chunk for chunk in all_chunks if chunk["full_doc_id"] == doc_id
                ]

            # 按chunk_order_index排序
            all_chunks.sort(
                key=lambda x: (x["full_doc_id"], x["chunk_order_index"])
            )

            total = len(all_chunks)

            # 分页
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paginated_chunks = all_chunks[start_idx:end_idx]

            return ChunkListResponse(
                total=total,
                page=page,
                page_size=page_size,
                chunks=paginated_chunks,
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"获取chunk列表失败: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"获取chunk列表失败: {str(e)}")

    @router.get(
        "/chunks/{chunk_id}",
        dependencies=[Depends(combined_auth)],
        summary="获取chunk详情",
        description="""
获取指定chunk的详细信息，包括文本内容、关联的实体和关系。

**返回内容**：
- Chunk 基本信息（ID、内容、token数等）
- 关联的实体列表
- 关联的关系列表

**使用场景**：
- 查看chunk的完整信息
- 了解chunk中提取的实体和关系
- 调试知识图谱构建结果

**示例**：
```bash
curl -X GET "http://localhost:8020/chunks/chunk-abc123" \\
  -H "LIGHTRAG-WORKSPACE: my_workspace"
```
        """,
        responses={
            200: {
                "description": "成功返回chunk详情",
                "content": {
                    "application/json": {
                        "example": {
                            "status": "success",
                            "chunk": {
                                "chunk_id": "chunk-abc123",
                                "content": "特斯拉是一家美国电动汽车公司，由马斯克领导。",
                                "tokens": 50,
                                "full_doc_id": "doc-xyz789",
                                "chunk_order_index": 0
                            },
                            "entities": [
                                {
                                    "entity_name": "特斯拉",
                                    "entity_type": "ORGANIZATION",
                                    "description": "美国电动汽车公司"
                                },
                                {
                                    "entity_name": "马斯克",
                                    "entity_type": "PERSON",
                                    "description": "特斯拉CEO"
                                }
                            ],
                            "entities_count": 2,
                            "relations": [
                                {
                                    "source_entity": "马斯克",
                                    "target_entity": "特斯拉",
                                    "description": "马斯克领导特斯拉",
                                    "keywords": "领导",
                                    "weight": 1.0
                                }
                            ],
                            "relations_count": 1
                        }
                    }
                }
            },
            404: {"description": "Chunk不存在"},
            500: {"description": "服务器内部错误"}
        },
        tags=["文档分块管理 / Chunk Management"]
    )
    async def get_chunk_detail(
        request: Request,
        chunk_id: str = Query(..., description="Chunk ID"),
    ):
        """
        获取chunk详情

        参数:
        - chunk_id: chunk ID

        返回:
        - chunk: chunk详细信息
            - chunk_id: chunk ID
            - content: chunk内容
            - tokens: token数量
            - full_doc_id: 所属文档ID
            - chunk_order_index: chunk顺序索引
        - entities: 关联的实体列表
            - entity_name: 实体名称
            - entity_type: 实体类型
            - description: 实体描述
        - relations: 关联的关系列表
            - source_entity: 源实体
            - target_entity: 目标实体
            - description: 关系描述
        """
        try:
            # 获取chunk数据
            chunk_data = await rag.text_chunks.get_by_id(chunk_id)

            if not chunk_data:
                raise HTTPException(status_code=404, detail=f"Chunk '{chunk_id}' 不存在")

            # 获取与chunk关联的实体
            entities = []
            relations = []

            # 从entity_chunks存储中查找包含此chunk_id的实体
            if hasattr(rag.entity_chunks, "_data"):
                entity_chunks_dict = rag.entity_chunks._data

                for entity_name, chunk_list in entity_chunks_dict.items():
                    if chunk_id in chunk_list:
                        # 获取实体详情
                        entity_data = await rag.full_entities.get_by_id(entity_name)
                        if entity_data:
                            entities.append(
                                {
                                    "entity_name": entity_name,
                                    "entity_type": entity_data.get(
                                        "entity_type", "UNKNOWN"
                                    ),
                                    "description": entity_data.get("description", ""),
                                }
                            )

            # 从relation_chunks存储中查找包含此chunk_id的关系
            if hasattr(rag.relation_chunks, "_data"):
                relation_chunks_dict = rag.relation_chunks._data

                for relation_key, chunk_list in relation_chunks_dict.items():
                    if chunk_id in chunk_list:
                        # relation_key格式: "source_entity<SEP>target_entity"
                        parts = relation_key.split("<SEP>")
                        if len(parts) == 2:
                            src_entity, tgt_entity = parts

                            # 获取关系详情
                            relation_data = await rag.full_relations.get_by_id(
                                relation_key
                            )

                            if relation_data:
                                relations.append(
                                    {
                                        "source_entity": src_entity,
                                        "target_entity": tgt_entity,
                                        "description": relation_data.get(
                                            "description", ""
                                        ),
                                        "keywords": relation_data.get("keywords", ""),
                                        "weight": relation_data.get("weight", 1.0),
                                    }
                                )

            return {
                "status": "success",
                "chunk": {
                    "chunk_id": chunk_id,
                    "content": chunk_data.get("content", ""),
                    "tokens": chunk_data.get("tokens", 0),
                    "full_doc_id": chunk_data.get("full_doc_id", ""),
                    "chunk_order_index": chunk_data.get("chunk_order_index", 0),
                },
                "entities": entities,
                "entities_count": len(entities),
                "relations": relations,
                "relations_count": len(relations),
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"获取chunk详情失败 '{chunk_id}': {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"获取chunk详情失败: {str(e)}")

    @router.get(
        "/documents/{doc_id}/chunks",
        dependencies=[Depends(combined_auth)],
        summary="获取文档的所有chunks",
        description="""
获取指定文档的所有分块，按顺序索引排序。

**使用场景**：
- 查看文档的完整分块结构
- 了解文档被切分的粒度
- 重建文档的原始内容顺序

**示例**：
```bash
curl -X GET "http://localhost:8020/documents/doc-xyz789/chunks" \\
  -H "LIGHTRAG-WORKSPACE: my_workspace"
```

**注意**：Chunks 按 `chunk_order_index` 排序，保持原文档顺序。
        """,
        responses={
            200: {
                "description": "成功返回文档的所有chunks",
                "content": {
                    "application/json": {
                        "example": {
                            "status": "success",
                            "doc_id": "doc-xyz789",
                            "chunks_count": 5,
                            "chunks": [
                                {
                                    "chunk_id": "chunk-001",
                                    "content": "第一段内容...",
                                    "tokens": 100,
                                    "chunk_order_index": 0
                                },
                                {
                                    "chunk_id": "chunk-002",
                                    "content": "第二段内容...",
                                    "tokens": 120,
                                    "chunk_order_index": 1
                                }
                            ]
                        }
                    }
                }
            },
            404: {"description": "文档不存在"},
            501: {"description": "当前存储后端不支持此操作"},
            500: {"description": "服务器内部错误"}
        },
        tags=["文档分块管理 / Chunk Management"]
    )
    async def get_document_chunks(
        request: Request,
        doc_id: str = Query(..., description="文档ID"),
    ):
        """
        获取文档的所有chunks

        参数:
        - doc_id: 文档ID

        返回:
        - doc_id: 文档ID
        - chunks_count: chunk数量
        - chunks: chunk列表 (按顺序排序)
        """
        try:
            # 从text_chunks存储中获取该文档的所有chunks
            if hasattr(rag.text_chunks, "_data"):
                all_chunks_dict = rag.text_chunks._data
            else:
                raise HTTPException(
                    status_code=501,
                    detail="当前存储后端不支持列出文档chunks，请使用JSON存储",
                )

            # 筛选出属于该文档的chunks
            doc_chunks = []
            for chunk_id, chunk_data in all_chunks_dict.items():
                if chunk_data.get("full_doc_id") == doc_id:
                    chunk_info = {
                        "chunk_id": chunk_id,
                        "content": chunk_data.get("content", ""),
                        "tokens": chunk_data.get("tokens", 0),
                        "chunk_order_index": chunk_data.get("chunk_order_index", 0),
                    }
                    doc_chunks.append(chunk_info)

            # 按chunk_order_index排序
            doc_chunks.sort(key=lambda x: x["chunk_order_index"])

            if not doc_chunks:
                # 检查文档是否存在
                doc_exists = await rag.full_docs.get_by_id(doc_id)
                if not doc_exists:
                    raise HTTPException(
                        status_code=404, detail=f"文档 '{doc_id}' 不存在"
                    )

            return {
                "status": "success",
                "doc_id": doc_id,
                "chunks_count": len(doc_chunks),
                "chunks": doc_chunks,
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"获取文档chunks失败 '{doc_id}': {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"获取文档chunks失败: {str(e)}")

    return router

