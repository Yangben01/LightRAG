"""
实体和关系管理路由
提供实体库、关系库的查询接口
支持多租户数据隔离（通过 workspace）
"""

from typing import Optional, List, Dict, Any
import traceback
from fastapi import APIRouter, Depends, Query, Path, HTTPException, Request
from pydantic import BaseModel, Field

from lightrag.utils import logger
from ..utils_api import get_combined_auth_dependency

router = APIRouter(
    tags=["实体和关系管理 / Entity & Relation Management"]
)


class EntityListResponse(BaseModel):
    """实体列表响应"""

    total: int = Field(..., description="总实体数量")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")
    entities: List[Dict[str, Any]] = Field(..., description="实体列表")


class RelationListResponse(BaseModel):
    """关系列表响应"""

    total: int = Field(..., description="总关系数量")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页数量")
    relations: List[Dict[str, Any]] = Field(..., description="关系列表")


def create_entity_relation_routes(rag, api_key: Optional[str] = None):
    """创建实体和关系管理路由"""
    combined_auth = get_combined_auth_dependency(api_key)

    def get_workspace_from_request(request: Request) -> str | None:
        """从请求头中提取 workspace 信息"""
        workspace = request.headers.get("LIGHTRAG-WORKSPACE", "").strip()
        return workspace if workspace else None

    @router.get(
        "/entities/list",
        dependencies=[Depends(combined_auth)],
        response_model=EntityListResponse,
        summary="获取实体列表",
        description="""
获取知识图谱中的所有实体，支持分页、类型筛选和名称搜索。

**多租户支持**：通过 `LIGHTRAG-WORKSPACE` 请求头指定工作空间，实现数据隔离。

**使用场景**：
- 浏览知识库中的所有实体
- 按类型查看特定类别的实体（如人物、组织、地点）
- 搜索特定名称的实体
```
        """,
        responses={
            200: {
                "description": "成功返回实体列表",
                "content": {
                    "application/json": {
                        "example": {
                            "total": 150,
                            "page": 1,
                            "page_size": 20,
                            "entities": [
                                {
                                    "entity_name": "特斯拉",
                                    "entity_id": "特斯拉",
                                    "entity_type": "ORGANIZATION",
                                    "description": "美国电动汽车和清洁能源公司",
                                    "source_id": "chunk-123",
                                    "degree": 5
                                }
                            ]
                        }
                    }
                }
            },
            500: {"description": "服务器内部错误"}
        },
        tags=["实体管理 / Entity Management"]
    )
    async def list_entities(
        request: Request,
        page: int = Query(1, ge=1, description="页码，从1开始"),
        page_size: int = Query(50, ge=1, le=500, description="每页数量，最大500"),
        entity_type: Optional[str] = Query(
            None, description="按实体类型筛选，例如: PERSON, ORGANIZATION, LOCATION"
        ),
        search: Optional[str] = Query(None, description="搜索实体名称 (模糊匹配)"),
    ):
        """
        获取实体列表，支持分页和筛选

        参数:
        - page: 页码 (从1开始)
        - page_size: 每页数量 (1-500)
        - entity_type: 实体类型筛选 (可选)
        - search: 实体名称搜索 (可选，模糊匹配)

        返回:
        - total: 总实体数量
        - page: 当前页码
        - page_size: 每页数量
        - entities: 实体列表，每个实体包含:
            - entity_name: 实体名称
            - entity_type: 实体类型
            - description: 实体描述
            - source_id: 来源chunk ID
            - degree: 节点度数 (连接数)
        """
        try:
            # 获取所有节点
            all_nodes = await rag.chunk_entity_relation_graph.get_all_nodes()

            # 按类型筛选
            if entity_type:
                all_nodes = [
                    node
                    for node in all_nodes
                    if node.get("entity_type", "").upper() == entity_type.upper()
                ]

            # 按名称搜索
            if search:
                search_lower = search.lower()
                all_nodes = [
                    node
                    for node in all_nodes
                    if search_lower
                    in node.get("entity_name", "").lower()
                    or search_lower in node.get("entity_id", "").lower()
                ]

            total = len(all_nodes)

            # 分页
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paginated_nodes = all_nodes[start_idx:end_idx]

            # 获取节点度数
            entity_names = [node.get("entity_id") for node in paginated_nodes]
            degrees = await rag.chunk_entity_relation_graph.node_degrees_batch(
                entity_names
            )

            # 格式化返回数据
            entities = []
            for node in paginated_nodes:
                entity_id = node.get("entity_id")
                entity_data = {
                    "entity_name": node.get("entity_name", entity_id),
                    "entity_id": entity_id,
                    "entity_type": node.get("entity_type", "UNKNOWN"),
                    "description": node.get("description", ""),
                    "source_id": node.get("source_id", ""),
                    "degree": degrees.get(entity_id, 0),
                }
                entities.append(entity_data)

            return EntityListResponse(
                total=total,
                page=page,
                page_size=page_size,
                entities=entities,
            )

        except Exception as e:
            logger.error(f"获取实体列表失败: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"获取实体列表失败: {str(e)}")

    @router.get(
        "/entities/by-document",
        dependencies=[Depends(combined_auth)],
        summary="按文档查询实体",
        description="""
根据文档 ID 或文件路径查询该文档关联的所有实体，支持分页。

**多租户支持**：通过 `LIGHTRAG-WORKSPACE` 请求头指定工作空间。

**查询方式**：
- 优先使用 `doc_id`（文档 ID，即 full_doc_id）- **推荐方式**
- 或使用 `file_path`（文档文件路径）- 备选方式

**推荐使用 `doc_id`**，因为：
- ✅ 更准确：文档 ID 是唯一标识，不会重复
- ✅ 性能更好：可以在 full_doc_id 上建立索引
- ✅ 数据稳定：不会因为文件移动而改变

**分页参数**：
- `page`: 页码，从1开始（默认：1）
- `page_size`: 每页数量，最大500（默认：50）

**示例**：
```bash
# 通过文档 ID 查询（推荐，带分页）
curl -X GET "http://localhost:8020/entities/by-document?doc_id=doc-123&page=1&page_size=20" \\
  -H "LIGHTRAG-WORKSPACE: my_workspace"

# 通过文件路径查询（带分页）
curl -X GET "http://localhost:8020/entities/by-document?file_path=/path/to/document.pdf&page=1&page_size=20" \\
  -H "LIGHTRAG-WORKSPACE: my_workspace"
```
        """,
        responses={
            200: {
                "description": "成功返回实体列表（分页）",
                "content": {
                    "application/json": {
                        "example": {
                            "status": "success",
                            "doc_id": "doc-123",
                            "file_path": None,
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
                    }
                }
            },
            400: {"description": "参数错误：必须提供 doc_id 或 file_path"},
            500: {"description": "服务器内部错误"}
        },
        tags=["实体管理 / Entity Management"]
    )
    async def get_entities_by_document(
        request: Request,
        doc_id: Optional[str] = Query(None, description="文档 ID (full_doc_id)，推荐使用"),
        file_path: Optional[str] = Query(None, description="文档文件路径，备选方式"),
        page: int = Query(1, ge=1, description="页码，从1开始"),
        page_size: int = Query(50, ge=1, le=500, description="每页数量，最大500"),
    ):
        """
        按文档查询实体（支持分页）

        参数:
        - doc_id: 文档 ID（推荐）
        - file_path: 文档文件路径（备选）
        - page: 页码，从1开始（默认：1）
        - page_size: 每页数量，最大500（默认：50）

        返回:
        - status: 状态
        - doc_id: 文档 ID
        - file_path: 文档路径
        - total: 总实体数量
        - page: 当前页码
        - page_size: 每页数量
        - entities_count: 当前页实体数量
        - entities: 实体列表
        """
        try:
            # 参数验证
            if not doc_id and not file_path:
                raise HTTPException(
                    status_code=400,
                    detail="必须提供 doc_id 或 file_path 参数之一"
                )

            # 检查是否使用 PostgreSQL 向量存储
            entities_vdb = rag.entities_vdb
            if not hasattr(entities_vdb, "db") or entities_vdb.db is None:
                raise HTTPException(
                    status_code=500,
                    detail="当前存储后端不支持按文档查询实体，请使用 PostgreSQL 向量存储"
                )

            from lightrag.kg.postgres_impl import PostgreSQLDB
            if not isinstance(entities_vdb.db, PostgreSQLDB):
                raise HTTPException(
                    status_code=500,
                    detail="当前存储后端不支持按文档查询实体，请使用 PostgreSQL 向量存储"
                )

            db = entities_vdb.db

            # 计算分页偏移量
            offset = (page - 1) * page_size

            # 构建 COUNT 查询（获取总数）
            if doc_id:
                # 通过 full_doc_id 查询，full_doc_id 是全局唯一的，不需要 workspace
                count_sql = """
                SELECT COUNT(DISTINCT e.id) as total
                FROM LIGHTRAG_VDB_ENTITY e
                WHERE EXISTS (
                      SELECT 1
                      FROM LIGHTRAG_VDB_CHUNKS c
                      WHERE c.full_doc_id = $1
                        AND c.id = ANY(e.chunk_ids)
                  );
                """
                count_params = [doc_id]
                query_file_path = None
            else:
                # 通过 file_path 查询（备选方式），仍需要 workspace 来确保数据隔离
                workspace = get_workspace_from_request(request) or rag.workspace
                count_sql = """
                SELECT COUNT(DISTINCT e.id) as total
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
                  );
                """
                count_params = [workspace, file_path]
                query_file_path = file_path

            # 执行 COUNT 查询
            count_result = await db.query(count_sql, count_params, multirows=False)
            total = count_result.get("total", 0) if count_result else 0

            # 构建数据查询（带分页）
            if doc_id:
                # 通过 full_doc_id 查询（推荐方式），full_doc_id 是全局唯一的，不需要 workspace
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
                WHERE EXISTS (
                      SELECT 1
                      FROM LIGHTRAG_VDB_CHUNKS c
                      WHERE c.full_doc_id = $1
                        AND c.id = ANY(e.chunk_ids)
                  )
                ORDER BY create_time DESC
                LIMIT $2 OFFSET $3;
                """
                params = [doc_id, page_size, offset]
            else:
                # 通过 file_path 查询（备选方式），仍需要 workspace 来确保数据隔离
                workspace = get_workspace_from_request(request) or rag.workspace
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
                ORDER BY create_time DESC
                LIMIT $3 OFFSET $4;
                """
                params = [workspace, file_path, page_size, offset]

            # 执行数据查询
            results = await db.query(sql, params, multirows=True)

            # 处理结果
            entities = []
            for row in results:
                entity = {
                    "id": row.get("id"),
                    "entity_name": row.get("entity_name"),
                    "content": row.get("content"),
                    "chunk_ids": row.get("chunk_ids", []),
                    "file_path": row.get("file_path"),
                    "create_time": row.get("create_time"),
                    "update_time": row.get("update_time"),
                }
                entities.append(entity)

            return {
                "status": "success",
                "doc_id": doc_id,
                "file_path": query_file_path,
                "total": total,
                "page": page,
                "page_size": page_size,
                "entities_count": len(entities),
                "entities": entities,
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"按文档查询实体失败: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(
                status_code=500, detail=f"按文档查询实体失败: {str(e)}"
            )

    @router.get(
        "/entities/{entity_name}",
        dependencies=[Depends(combined_auth)],
        summary="获取实体详情",
        description="""
获取指定实体的详细信息，包括所有属性和关系网络。

**返回内容**：
- 实体的基本信息（名称、类型、描述）
- 实体的所有关系列表
- 节点度数（连接数）

**示例**：
```bash
curl -X GET "http://localhost:8020/entities/特斯拉" \\
  -H "LIGHTRAG-WORKSPACE: my_workspace"
```
        """,
        responses={
            200: {
                "description": "成功返回实体详情",
                "content": {
                    "application/json": {
                        "example": {
                            "status": "success",
                            "entity": {
                                "entity_name": "特斯拉",
                                "entity_id": "特斯拉",
                                "entity_type": "ORGANIZATION",
                                "description": "美国电动汽车和清洁能源公司",
                                "source_id": "chunk-123",
                                "degree": 5
                            },
                            "relations": [
                                {
                                    "source_entity": "马斯克",
                                    "target_entity": "特斯拉",
                                    "description": "马斯克是特斯拉的CEO",
                                    "keywords": "领导,创始人",
                                    "weight": 1.0,
                                    "source_id": "chunk-456"
                                }
                            ],
                            "relations_count": 5
                        }
                    }
                }
            },
            404: {"description": "实体不存在"},
            500: {"description": "服务器内部错误"}
        },
        tags=["实体管理 / Entity Management"]
    )
    async def get_entity_detail(
        request: Request,
        entity_name: str = Path(..., description="实体名称"),
    ):
        """
        获取实体详情

        参数:
        - entity_name: 实体名称

        返回:
        - entity: 实体详细信息
            - entity_name: 实体名称
            - entity_type: 实体类型
            - description: 实体描述
            - source_id: 来源chunk ID
            - degree: 节点度数
            - ...其他属性
        - relations: 关系列表
            - target_entity: 目标实体名称
            - relation_type: 关系类型
            - description: 关系描述
            - weight: 关系权重
        """
        try:
            # 从请求头中获取 workspace，对于 PostgreSQL 图存储需要临时设置 graph_name
            workspace = get_workspace_from_request(request)
            graph_storage = rag.chunk_entity_relation_graph
            original_graph_name = None
            original_workspace = None
            
            # 如果是 PostgreSQL 图存储，需要根据 workspace 临时设置 graph_name
            if hasattr(graph_storage, "graph_name") and hasattr(graph_storage, "_get_workspace_graph_name"):
                original_graph_name = graph_storage.graph_name
                original_workspace = graph_storage.workspace
                # 使用请求头中的 workspace，如果没有则使用存储实例的 workspace
                if workspace:
                    graph_storage.workspace = workspace
                # 重新生成 graph_name（即使 workspace 为 None，也要使用当前 workspace 重新生成）
                graph_storage.graph_name = graph_storage._get_workspace_graph_name()
                logger.debug(f"查询实体详情 '{entity_name}'，workspace: {graph_storage.workspace}, graph_name: {graph_storage.graph_name}")
            
            try:
                # 检查实体是否存在
                exists = await graph_storage.has_node(entity_name)
                if not exists:
                    logger.warning(f"实体 '{entity_name}' 在 workspace '{graph_storage.workspace}' (graph_name: {graph_storage.graph_name}) 中不存在")
                    raise HTTPException(status_code=404, detail=f"实体 '{entity_name}' 不存在")

                # 获取实体节点信息
                node = await graph_storage.get_node(entity_name)
                if not node:
                    raise HTTPException(status_code=404, detail=f"实体 '{entity_name}' 不存在")

                # 获取节点度数
                degree = await graph_storage.node_degree(entity_name)

                # 获取所有关系
                edges = await graph_storage.get_node_edges(entity_name)

                relations = []
                if edges:
                    for src, tgt in edges:
                        # 确定目标实体
                        target_entity = tgt if src == entity_name else src

                        # 获取边的详细信息
                        edge_data = await graph_storage.get_edge(
                            src, tgt
                        )

                        if edge_data:
                            relation_info = {
                                "source_entity": src,
                                "target_entity": target_entity,
                                "description": edge_data.get("description", ""),
                                "keywords": edge_data.get("keywords", ""),
                                "weight": edge_data.get("weight", 1.0),
                                "source_id": edge_data.get("source_id", ""),
                            }
                            relations.append(relation_info)

                # 组装返回数据
                entity_data = dict(node)
                entity_data["degree"] = degree
                entity_data["entity_id"] = entity_name

                return {
                    "status": "success",
                    "entity": entity_data,
                    "relations": relations,
                    "relations_count": len(relations),
                }
            finally:
                # 恢复原始的 graph_name 和 workspace
                if original_graph_name is not None:
                    graph_storage.graph_name = original_graph_name
                    if original_workspace is not None:
                        graph_storage.workspace = original_workspace

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"获取实体详情失败 '{entity_name}': {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"获取实体详情失败: {str(e)}")

    @router.get(
        "/relations/list",
        dependencies=[Depends(combined_auth)],
        response_model=RelationListResponse,
        summary="获取关系列表",
        description="""
获取知识图谱中的所有关系，支持分页、关键词搜索和实体筛选。

**多租户支持**：通过 `LIGHTRAG-WORKSPACE` 请求头指定工作空间。

**筛选选项**：
- 按关键词搜索关系描述
- 按实体名称筛选，查看该实体的所有关系

**示例**：
```bash
# 获取所有关系
curl -X GET "http://localhost:8020/relations/list?page=1&page_size=20" \\
  -H "LIGHTRAG-WORKSPACE: my_workspace"

# 筛选特定实体的关系
curl -X GET "http://localhost:8020/relations/list?entity_name=特斯拉" \\
  -H "LIGHTRAG-WORKSPACE: my_workspace"

# 按关键词搜索关系
curl -X GET "http://localhost:8020/relations/list?keyword=CEO" \\
  -H "LIGHTRAG-WORKSPACE: my_workspace"
```
        """,
        responses={
            200: {
                "description": "成功返回关系列表",
                "content": {
                    "application/json": {
                        "example": {
                            "total": 200,
                            "page": 1,
                            "page_size": 20,
                            "relations": [
                                {
                                    "source_entity": "马斯克",
                                    "target_entity": "特斯拉",
                                    "description": "马斯克是特斯拉的CEO",
                                    "keywords": "领导,创始人",
                                    "weight": 1.0,
                                    "source_id": "chunk-456"
                                }
                            ]
                        }
                    }
                }
            },
            500: {"description": "服务器内部错误"}
        },
        tags=["关系管理 / Relation Management"]
    )
    async def list_relations(
        page: int = Query(1, ge=1, description="页码，从1开始"),
        page_size: int = Query(50, ge=1, le=500, description="每页数量，最大500"),
        keyword: Optional[str] = Query(
            None, description="按关系关键词筛选 (模糊匹配)"
        ),
        entity_name: Optional[str] = Query(
            None, description="按实体名称筛选，返回与该实体相关的所有关系"
        ),
    ):
        """
        获取关系列表，支持分页和筛选

        参数:
        - page: 页码 (从1开始)
        - page_size: 每页数量 (1-500)
        - keyword: 关系关键词筛选 (可选，模糊匹配)
        - entity_name: 按实体筛选 (可选)

        返回:
        - total: 总关系数量
        - page: 当前页码
        - page_size: 每页数量
        - relations: 关系列表，每个关系包含:
            - source_entity: 源实体名称
            - target_entity: 目标实体名称
            - description: 关系描述
            - keywords: 关系关键词
            - weight: 关系权重
            - source_id: 来源chunk ID
        """
        try:
            # 获取所有边
            all_edges = await rag.chunk_entity_relation_graph.get_all_edges()

            # 按实体筛选
            if entity_name:
                all_edges = [
                    edge
                    for edge in all_edges
                    if edge.get("source") == entity_name
                    or edge.get("target") == entity_name
                ]

            # 按关键词筛选
            if keyword:
                keyword_lower = keyword.lower()
                all_edges = [
                    edge
                    for edge in all_edges
                    if keyword_lower in edge.get("keywords", "").lower()
                    or keyword_lower in edge.get("description", "").lower()
                ]

            total = len(all_edges)

            # 分页
            start_idx = (page - 1) * page_size
            end_idx = start_idx + page_size
            paginated_edges = all_edges[start_idx:end_idx]

            # 格式化返回数据
            relations = []
            for edge in paginated_edges:
                relation_data = {
                    "source_entity": edge.get("source"),
                    "target_entity": edge.get("target"),
                    "description": edge.get("description", ""),
                    "keywords": edge.get("keywords", ""),
                    "weight": edge.get("weight", 1.0),
                    "source_id": edge.get("source_id", ""),
                }
                relations.append(relation_data)

            return RelationListResponse(
                total=total,
                page=page,
                page_size=page_size,
                relations=relations,
            )

        except Exception as e:
            logger.error(f"获取关系列表失败: {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"获取关系列表失败: {str(e)}")

    @router.get(
        "/entities/{entity_name}/relations",
        dependencies=[Depends(combined_auth)],
        summary="获取实体的所有关系",
        description="""
获取指定实体的所有关系列表，不分页，返回该实体的完整关系网络。

**使用场景**：
- 查看实体的完整关系图谱
- 分析实体的连接模式

**示例**：
```bash
curl -X GET "http://localhost:8020/entities/特斯拉/relations" \\
  -H "LIGHTRAG-WORKSPACE: my_workspace"
```
        """,
        responses={
            200: {
                "description": "成功返回实体关系列表",
                "content": {
                    "application/json": {
                        "example": {
                            "status": "success",
                            "entity_name": "特斯拉",
                            "relations_count": 5,
                            "relations": [
                                {
                                    "source_entity": "马斯克",
                                    "target_entity": "特斯拉",
                                    "description": "马斯克是特斯拉的CEO",
                                    "keywords": "领导,创始人",
                                    "weight": 1.0,
                                    "source_id": "chunk-456"
                                }
                            ]
                        }
                    }
                }
            },
            404: {"description": "实体不存在"},
            500: {"description": "服务器内部错误"}
        },
        tags=["关系管理 / Relation Management"]
    )
    async def get_entity_relations(
        request: Request,
        entity_name: str = Path(..., description="实体名称"),
    ):
        """
        获取实体的所有关系

        参数:
        - entity_name: 实体名称

        返回:
        - entity_name: 实体名称
        - relations_count: 关系数量
        - relations: 关系列表
        """
        try:
            # 从请求头中获取 workspace，对于 PostgreSQL 图存储需要临时设置 graph_name
            workspace = get_workspace_from_request(request)
            graph_storage = rag.chunk_entity_relation_graph
            original_graph_name = None
            original_workspace = None
            
            # 如果是 PostgreSQL 图存储，需要根据 workspace 临时设置 graph_name
            if hasattr(graph_storage, "graph_name") and hasattr(graph_storage, "_get_workspace_graph_name"):
                original_graph_name = graph_storage.graph_name
                original_workspace = graph_storage.workspace
                # 使用请求头中的 workspace，如果没有则使用存储实例的 workspace
                if workspace:
                    graph_storage.workspace = workspace
                # 重新生成 graph_name（即使 workspace 为 None，也要使用当前 workspace 重新生成）
                graph_storage.graph_name = graph_storage._get_workspace_graph_name()
                logger.debug(f"查询实体关系 '{entity_name}'，workspace: {graph_storage.workspace}, graph_name: {graph_storage.graph_name}")
            
            try:
                # 检查实体是否存在
                exists = await graph_storage.has_node(entity_name)
                if not exists:
                    logger.warning(f"实体 '{entity_name}' 在 workspace '{graph_storage.workspace}' (graph_name: {graph_storage.graph_name}) 中不存在")
                    raise HTTPException(status_code=404, detail=f"实体 '{entity_name}' 不存在")

                # 获取所有关系
                edges = await graph_storage.get_node_edges(entity_name)

                relations = []
                if edges:
                    for src, tgt in edges:
                        # 确定目标实体
                        target_entity = tgt if src == entity_name else src

                        # 获取边的详细信息
                        edge_data = await graph_storage.get_edge(
                            src, tgt
                        )

                        if edge_data:
                            relation_info = {
                                "source_entity": src,
                                "target_entity": target_entity,
                                "description": edge_data.get("description", ""),
                                "keywords": edge_data.get("keywords", ""),
                                "weight": edge_data.get("weight", 1.0),
                                "source_id": edge_data.get("source_id", ""),
                            }
                            relations.append(relation_info)

                return {
                    "status": "success",
                    "entity_name": entity_name,
                    "relations_count": len(relations),
                    "relations": relations,
                }
            finally:
                # 恢复原始的 graph_name 和 workspace
                if original_graph_name is not None:
                    graph_storage.graph_name = original_graph_name
                    if original_workspace is not None:
                        graph_storage.workspace = original_workspace

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"获取实体关系失败 '{entity_name}': {str(e)}")
            logger.error(traceback.format_exc())
            raise HTTPException(status_code=500, detail=f"获取实体关系失败: {str(e)}")

    return router

