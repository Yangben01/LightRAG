"""
This module contains all query-related routes for the LightRAG API.
"""

import json
from typing import Any, Dict, List, Literal, Optional
from fastapi import APIRouter, Depends, HTTPException
from lightrag.base import QueryParam
from lightrag.api.utils_api import get_combined_auth_dependency
from lightrag.utils import logger
from pydantic import BaseModel, Field, field_validator

router = APIRouter(tags=["query"])


class QueryRequest(BaseModel):
    query: str = Field(
        min_length=3,
        description="查询文本",
    )

    mode: Literal["local", "global", "hybrid", "naive", "mix", "bypass"] = Field(
        default="mix",
        description="查询模式",
    )

    only_need_context: Optional[bool] = Field(
        default=None,
        description="如果为True，则只返回检索到的上下文而不生成响应。",
    )

    only_need_prompt: Optional[bool] = Field(
        default=None,
        description="如果为True，则只返回生成的提示而不产生响应。",
    )

    response_type: Optional[str] = Field(
        min_length=1,
        default=None,
        description="定义响应格式。示例: '多个段落', '单个段落', '要点'。",
    )

    top_k: Optional[int] = Field(
        ge=1,
        default=None,
        description="要检索的顶级项目数。在'local'模式中表示实体，在'global'模式中表示关系。",
    )

    chunk_top_k: Optional[int] = Field(
        ge=1,
        default=None,
        description="最初从向量搜索中检索的文本块数量以及重新排序后保留的数量。",
    )

    max_entity_tokens: Optional[int] = Field(
        default=None,
        description="在统一代币控制系统中为实体上下文分配的最大代币数。",
        ge=1,
    )

    max_relation_tokens: Optional[int] = Field(
        default=None,
        description="在统一代币控制系统中为关系上下文分配的最大代币数。",
        ge=1,
    )

    max_total_tokens: Optional[int] = Field(
        default=None,
        description="整个查询上下文（实体+关系+块+系统提示）的最大总代币预算。",
        ge=1,
    )

    hl_keywords: list[str] = Field(
        default_factory=list,
        description="在检索中优先考虑的高级关键词列表。留空让LLM生成关键词。",
    )

    ll_keywords: list[str] = Field(
        default_factory=list,
        description="细化检索焦点的低级关键词列表。留空让LLM生成关键词。",
    )

    conversation_history: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="存储过去的对话历史以保持上下文。格式: [{'role': 'user/assistant', 'content': 'message'}]。",
    )

    user_prompt: Optional[str] = Field(
        default=None,
        description="用户提供的查询提示。如果提供，将使用此提示而不是提示模板中的默认值。",
    )

    enable_rerank: Optional[bool] = Field(
        default=None,
        description="启用重新排序检索到的文本块。如果为True但未配置重新排序模型，将发出警告。默认为True。",
    )

    include_references: Optional[bool] = Field(
        default=True,
        description="如果为True，则在响应中包含参考文献列表。影响/query和/query/stream端点。/query/data总是包含参考文献。",
    )

    include_chunk_content: Optional[bool] = Field(
        default=False,
        description="如果为True，则在参考文献中包含实际的块文本内容。仅在include_references=True时适用。适用于评估和调试。",
    )

    stream: Optional[bool] = Field(
        default=True,
        description="如果为True，则启用流式输出以实现实时响应。仅影响/query/stream端点。",
    )

    @field_validator("query", mode="after")
    @classmethod
    def query_strip_after(cls, query: str) -> str:
        return query.strip()

    @field_validator("conversation_history", mode="after")
    @classmethod
    def conversation_history_role_check(
        cls, conversation_history: List[Dict[str, Any]] | None
    ) -> List[Dict[str, Any]] | None:
        if conversation_history is None:
            return None
        for msg in conversation_history:
            if "role" not in msg:
                raise ValueError("Each message must have a 'role' key.")
            if not isinstance(msg["role"], str) or not msg["role"].strip():
                raise ValueError("Each message 'role' must be a non-empty string.")
        return conversation_history

    def to_query_params(self, is_stream: bool) -> "QueryParam":
        """Converts a QueryRequest instance into a QueryParam instance."""
        # Use Pydantic's `.model_dump(exclude_none=True)` to remove None values automatically
        # Exclude API-level parameters that don't belong in QueryParam
        request_data = self.model_dump(
            exclude_none=True, exclude={"query", "include_chunk_content"}
        )

        # Ensure `mode` and `stream` are set explicitly
        param = QueryParam(**request_data)
        param.stream = is_stream
        return param


class ReferenceItem(BaseModel):
    """查询响应中的单个参考项。"""

    reference_id: str = Field(description="唯一的参考标识符")
    file_path: str = Field(description="源文件路径")
    content: Optional[List[str]] = Field(
        default=None,
        description="来自此文件的块内容列表（仅在include_chunk_content=True时存在）",
    )


class QueryResponse(BaseModel):
    response: str = Field(
        description="生成的响应",
    )
    references: Optional[List[ReferenceItem]] = Field(
        default=None,
        description="参考文献列表（当include_references=False时禁用，/query/data总是包含参考文献。）",
    )


class QueryDataResponse(BaseModel):
    status: str = Field(description="查询执行状态")
    message: str = Field(description="状态消息")
    data: Dict[str, Any] = Field(
        description="包含实体、关系、块和参考文献的查询结果数据"
    )
    metadata: Dict[str, Any] = Field(
        description="包含模式、关键字和处理信息的查询元数据"
    )


class StreamChunkResponse(BaseModel):
    """NDJSON格式的流式块响应模型"""

    references: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description="参考文献列表（仅在include_references=True时的第一个块中）",
    )
    response: Optional[str] = Field(
        default=None, description="响应内容块或完整响应"
    )
    error: Optional[str] = Field(
        default=None, description="处理失败时的错误消息"
    )


def create_query_routes(rag, api_key: Optional[str] = None, top_k: int = 60):
    combined_auth = get_combined_auth_dependency(api_key)

    @router.post(
        "/query",
        response_model=QueryResponse,
        dependencies=[Depends(combined_auth)],
        responses={
            200: {
                "description": "成功的RAG查询响应",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "response": {
                                    "type": "string",
                                    "description": "来自RAG系统的生成响应",
                                },
                                "references": {
                                    "type": "array",
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "reference_id": {"type": "string"},
                                            "file_path": {"type": "string"},
                                            "content": {
                                                "type": "array",
                                                "items": {"type": "string"},
                                                "description": "来自此文件的块内容列表（仅在include_chunk_content=True时包含）",
                                            },
                                        },
                                    },
                                    "description": "参考文献列表（仅在include_references=True时包含）",
                                },
                            },
                            "required": ["response"],
                        },
                        "examples": {
                            "with_references": {
                                "summary": "带参考文献的响应",
                                "description": "include_references=True时的响应示例",
                                "value": {
                                    "response": "人工智能（AI）是计算机科学的一个分支，旨在创造能够执行通常需要人类智能的任务的智能机器，如学习、推理和解决问题。",
                                    "references": [
                                        {
                                            "reference_id": "1",
                                            "file_path": "/documents/ai_overview.pdf",
                                        },
                                        {
                                            "reference_id": "2",
                                            "file_path": "/documents/machine_learning.txt",
                                        },
                                    ],
                                },
                            },
                            "with_chunk_content": {
                                "summary": "带块内容的响应",
                                "description": "include_references=True且include_chunk_content=True时的响应示例。注意：内容是同一文件的块数组。",
                                "value": {
                                    "response": "人工智能（AI）是计算机科学的一个分支，旨在创造能够执行通常需要人类智能的任务的智能机器，如学习、推理和解决问题。",
                                    "references": [
                                        {
                                            "reference_id": "1",
                                            "file_path": "/documents/ai_overview.pdf",
                                            "content": [
                                                "人工智能（AI）是计算机科学中一个变革性的领域，专注于创建能够执行需要类似人类智能任务的系统。这些任务包括从经验中学习、理解自然语言、识别模式和做出决策。",
                                                "AI系统可以分为窄AI（为特定任务设计）和通用AI（旨在匹配人类在广泛领域的认知能力）。",
                                            ],
                                        },
                                        {
                                            "reference_id": "2",
                                            "file_path": "/documents/machine_learning.txt",
                                            "content": [
                                                "机器学习是AI的一个子集，使计算机能够从经验中学习和改进，而无需明确编程。它专注于开发能够访问数据并使用数据进行自我学习的算法。"
                                            ],
                                        },
                                    ],
                                },
                            },
                            "without_references": {
                                "summary": "不带参考文献的响应",
                                "description": "include_references=False时的响应示例",
                                "value": {
                                    "response": "人工智能（AI）是计算机科学的一个分支，旨在创造能够执行通常需要人类智能的任务的智能机器，如学习、推理和解决问题。"
                                },
                            },
                            "different_modes": {
                                "summary": "不同的查询模式",
                                "description": "不同查询模式的响应示例",
                                "value": {
                                    "local_mode": "关注特定实体及其关系",
                                    "global_mode": "提供来自关系模式的更广泛上下文",
                                    "hybrid_mode": "结合本地和全局方法",
                                    "naive_mode": "简单的向量相似性搜索",
                                    "mix_mode": "集成知识图谱和向量检索",
                                },
                            },
                        },
                    }
                },
            },
            400: {
                "description": "错误请求 - 无效的输入参数",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {"detail": {"type": "string"}},
                        },
                        "example": {
                            "detail": "查询文本长度必须至少为3个字符"
                        },
                    }
                },
            },
            500: {
                "description": "内部服务器错误 - 查询处理失败",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {"detail": {"type": "string"}},
                        },
                        "example": {
                            "detail": "处理查询失败：LLM服务不可用"
                        },
                    }
                },
            },
        },
    )
    async def query_text(request: QueryRequest):
        """
        Comprehensive RAG query endpoint with non-streaming response. Parameter "stream" is ignored.

        This endpoint performs Retrieval-Augmented Generation (RAG) queries using various modes
        to provide intelligent responses based on your knowledge base.

        **Query Modes:**
        - **local**: Focuses on specific entities and their direct relationships
        - **global**: Analyzes broader patterns and relationships across the knowledge graph
        - **hybrid**: Combines local and global approaches for comprehensive results
        - **naive**: Simple vector similarity search without knowledge graph
        - **mix**: Integrates knowledge graph retrieval with vector search (recommended)
        - **bypass**: Direct LLM query without knowledge retrieval

        conversation_history parameteris sent to LLM only, does not affect retrieval results.

        **Usage Examples:**

        Basic query:
        ```json
        {
            "query": "What is machine learning?",
            "mode": "mix"
        }
        ```

        Bypass initial LLM call by providing high-level and low-level keywords:
        ```json
        {
            "query": "What is Retrieval-Augmented-Generation?",
            "hl_keywords": ["machine learning", "information retrieval", "natural language processing"],
            "ll_keywords": ["retrieval augmented generation", "RAG", "knowledge base"],
            "mode": "mix"
        }
        ```

        Advanced query with references:
        ```json
        {
            "query": "Explain neural networks",
            "mode": "hybrid",
            "include_references": true,
            "response_type": "Multiple Paragraphs",
            "top_k": 10
        }
        ```

        Conversation with history:
        ```json
        {
            "query": "Can you give me more details?",
            "conversation_history": [
                {"role": "user", "content": "What is AI?"},
                {"role": "assistant", "content": "AI is artificial intelligence..."}
            ]
        }
        ```

        Args:
            request (QueryRequest): The request object containing query parameters:
                - **query**: The question or prompt to process (min 3 characters)
                - **mode**: Query strategy - "mix" recommended for best results
                - **include_references**: Whether to include source citations
                - **response_type**: Format preference (e.g., "Multiple Paragraphs")
                - **top_k**: Number of top entities/relations to retrieve
                - **conversation_history**: Previous dialogue context
                - **max_total_tokens**: Token budget for the entire response

        Returns:
            QueryResponse: JSON response containing:
                - **response**: The generated answer to your query
                - **references**: Source citations (if include_references=True)

        Raises:
            HTTPException:
                - 400: Invalid input parameters (e.g., query too short)
                - 500: Internal processing error (e.g., LLM service unavailable)
        """
        try:
            param = request.to_query_params(
                False
            )  # Ensure stream=False for non-streaming endpoint
            # Force stream=False for /query endpoint regardless of include_references setting
            param.stream = False

            # Unified approach: always use aquery_llm for both cases
            result = await rag.aquery_llm(request.query, param=param)

            # Extract LLM response and references from unified result
            llm_response = result.get("llm_response", {})
            data = result.get("data", {})
            references = data.get("references", [])

            # Get the non-streaming response content
            response_content = llm_response.get("content", "")
            if not response_content:
                response_content = "No relevant context found for the query."

            # Enrich references with chunk content if requested
            if request.include_references and request.include_chunk_content:
                chunks = data.get("chunks", [])
                # Create a mapping from reference_id to chunk content
                ref_id_to_content = {}
                for chunk in chunks:
                    ref_id = chunk.get("reference_id", "")
                    content = chunk.get("content", "")
                    if ref_id and content:
                        # Collect chunk content; join later to avoid quadratic string concatenation
                        ref_id_to_content.setdefault(ref_id, []).append(content)

                # Add content to references
                enriched_references = []
                for ref in references:
                    ref_copy = ref.copy()
                    ref_id = ref.get("reference_id", "")
                    if ref_id in ref_id_to_content:
                        # Keep content as a list of chunks (one file may have multiple chunks)
                        ref_copy["content"] = ref_id_to_content[ref_id]
                    enriched_references.append(ref_copy)
                references = enriched_references

            # Return response with or without references based on request
            if request.include_references:
                return QueryResponse(response=response_content, references=references)
            else:
                return QueryResponse(response=response_content, references=None)
        except Exception as e:
            logger.error(f"Error processing query: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @router.post(
        "/query/stream",
        dependencies=[Depends(combined_auth)],
        responses={
            200: {
                "description": "灵活的RAG查询响应 - 格式取决于流参数",
                "content": {
                    "application/x-ndjson": {
                        "schema": {
                            "type": "string",
                            "format": "ndjson",
                            "description": "用于流式和非流式响应的换行分隔JSON（NDJSON）格式。对于流式：多行包含独立的JSON对象。对于非流式：单行包含完整的JSON对象。",
                            "example": '{"references": [{"reference_id": "1", "file_path": "/documents/ai.pdf"}]}\n{"response": "人工智能是"}\n{"response": " 计算机科学的一个领域"}\n{"response": " 专注于创造智能机器。"}',
                        },
                        "examples": {
                            "streaming_with_references": {
                                "summary": "带参考文献的流式模式（stream=true）",
                                "description": "当stream=True且include_references=True时的多个NDJSON行。第一行包含参考文献，后续行包含响应块。",
                                "value": '{"references": [{"reference_id": "1", "file_path": "/documents/ai_overview.pdf"}, {"reference_id": "2", "file_path": "/documents/ml_basics.txt"}]}\n{"response": "人工智能（AI）是计算机科学的一个分支"}\n{"response": " 旨在创造能够执行智能机器"}\n{"response": " 通常需要人类智能的任务，如学习，"}\n{"response": " 推理和解决问题。"}',
                            },
                            "streaming_with_chunk_content": {
                                "summary": "带块内容的流式模式（stream=true, include_chunk_content=true）",
                                "description": "当stream=True、include_references=True且include_chunk_content=True时的多个NDJSON行。第一行包含带有内容数组的参考文献（一个文件可能有多个块），后续行包含响应块。",
                                "value": '{"references": [{"reference_id": "1", "file_path": "/documents/ai_overview.pdf", "content": ["人工智能（AI）是一个变革性领域...", "AI系统可分为窄AI和通用AI..."]}, {"reference_id": "2", "file_path": "/documents/ml_basics.txt", "content": ["机器学习是AI的一个子集，使计算机能够学习..."]}]}\n{"response": "人工智能（AI）是计算机科学的一个分支"}\n{"response": " 旨在创造能够执行智能机器"}\n{"response": " 通常需要人类智能的任务。"}',
                            },
                            "streaming_without_references": {
                                "summary": "不带参考文献的流式模式（stream=true）",
                                "description": "当stream=True且include_references=False时的多个NDJSON行。只发送响应块。",
                                "value": '{"response": "机器学习是人工智能的一个子集"}\n{"response": " 使计算机能够从经验中学习和改进"}\n{"response": " 而无需为每个任务明确编程。"}',
                            },
                            "non_streaming_with_references": {
                                "summary": "带参考文献的非流式模式（stream=false）",
                                "description": "当stream=False且include_references=True时的单个NDJSON行。一条消息中包含完整响应和参考文献。",
                                "value": '{"references": [{"reference_id": "1", "file_path": "/documents/neural_networks.pdf"}], "response": "神经网络是受生物神经网络启发的计算模型，由互连的节点（神经元）组成，按层组织。它们是深度学习的基础，可以通过训练过程从数据中学习复杂的模式。"}',
                            },
                            "non_streaming_without_references": {
                                "summary": "不带参考文献的非流式模式（stream=false）",
                                "description": "当stream=False且include_references=False时的单个NDJSON行。仅包含完整响应。",
                                "value": '{"response": "深度学习是机器学习的一个子集，使用具有多层的神经网络（因此称为深度）来建模和理解数据中的复杂模式。它已经彻底改变了计算机视觉、自然语言处理和语音识别等领域。"}',
                            },
                            "error_response": {
                                "summary": "流式处理期间的错误",
                                "description": "处理过程中发生错误时的NDJSON格式错误处理。",
                                "value": '{"references": [{"reference_id": "1", "file_path": "/documents/ai.pdf"}]}\n{"response": "人工智能是"}\n{"error": "LLM服务暂时不可用"}',
                            },
                        },
                    }
                },
            },
            400: {
                "description": "错误请求 - 无效的输入参数",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {"detail": {"type": "string"}},
                        },
                        "example": {
                            "detail": "查询文本长度必须至少为3个字符"
                        },
                    }
                },
            },
            500: {
                "description": "内部服务器错误 - 查询处理失败",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {"detail": {"type": "string"}},
                        },
                        "example": {
                            "detail": "处理流式查询失败：知识图谱不可用"
                        },
                    }
                },
            },
        },
    )
    async def query_text_stream(request: QueryRequest):
        """
        Advanced RAG query endpoint with flexible streaming response.

        This endpoint provides the most flexible querying experience, supporting both real-time streaming
        and complete response delivery based on your integration needs.

        **Response Modes:**
        - Real-time response delivery as content is generated
        - NDJSON format: each line is a separate JSON object
        - First line: `{"references": [...]}` (if include_references=True)
        - Subsequent lines: `{"response": "content chunk"}`
        - Error handling: `{"error": "error message"}`

        > If stream parameter is False, or the query hit LLM cache, complete response delivered in a single streaming message.

        **Response Format Details**
        - **Content-Type**: `application/x-ndjson` (Newline-Delimited JSON)
        - **Structure**: Each line is an independent, valid JSON object
        - **Parsing**: Process line-by-line, each line is self-contained
        - **Headers**: Includes cache control and connection management

        **Query Modes (same as /query endpoint)**
        - **local**: Entity-focused retrieval with direct relationships
        - **global**: Pattern analysis across the knowledge graph
        - **hybrid**: Combined local and global strategies
        - **naive**: Vector similarity search only
        - **mix**: Integrated knowledge graph + vector retrieval (recommended)
        - **bypass**: Direct LLM query without knowledge retrieval

        conversation_history parameteris sent to LLM only, does not affect retrieval results.

        **Usage Examples**

        Real-time streaming query:
        ```json
        {
            "query": "Explain machine learning algorithms",
            "mode": "mix",
            "stream": true,
            "include_references": true
        }
        ```

        Bypass initial LLM call by providing high-level and low-level keywords:
        ```json
        {
            "query": "What is Retrieval-Augmented-Generation?",
            "hl_keywords": ["machine learning", "information retrieval", "natural language processing"],
            "ll_keywords": ["retrieval augmented generation", "RAG", "knowledge base"],
            "mode": "mix"
        }
        ```

        Complete response query:
        ```json
        {
            "query": "What is deep learning?",
            "mode": "hybrid",
            "stream": false,
            "response_type": "Multiple Paragraphs"
        }
        ```

        Conversation with context:
        ```json
        {
            "query": "Can you elaborate on that?",
            "stream": true,
            "conversation_history": [
                {"role": "user", "content": "What is neural network?"},
                {"role": "assistant", "content": "A neural network is..."}
            ]
        }
        ```

        **Response Processing:**

        ```python
        async for line in response.iter_lines():
            data = json.loads(line)
            if "references" in data:
                # Handle references (first message)
                references = data["references"]
            if "response" in data:
                # Handle content chunk
                content_chunk = data["response"]
            if "error" in data:
                # Handle error
                error_message = data["error"]
        ```

        **Error Handling:**
        - Streaming errors are delivered as `{"error": "message"}` lines
        - Non-streaming errors raise HTTP exceptions
        - Partial responses may be delivered before errors in streaming mode
        - Always check for error objects when processing streaming responses

        Args:
            request (QueryRequest): The request object containing query parameters:
                - **query**: The question or prompt to process (min 3 characters)
                - **mode**: Query strategy - "mix" recommended for best results
                - **stream**: Enable streaming (True) or complete response (False)
                - **include_references**: Whether to include source citations
                - **response_type**: Format preference (e.g., "Multiple Paragraphs")
                - **top_k**: Number of top entities/relations to retrieve
                - **conversation_history**: Previous dialogue context for multi-turn conversations
                - **max_total_tokens**: Token budget for the entire response

        Returns:
            StreamingResponse: NDJSON streaming response containing:
                - **Streaming mode**: Multiple JSON objects, one per line
                  - References object (if requested): `{"references": [...]}`
                  - Content chunks: `{"response": "chunk content"}`
                  - Error objects: `{"error": "error message"}`
                - **Non-streaming mode**: Single JSON object
                  - Complete response: `{"references": [...], "response": "complete content"}`

        Raises:
            HTTPException:
                - 400: Invalid input parameters (e.g., query too short, invalid mode)
                - 500: Internal processing error (e.g., LLM service unavailable)

        Note:
            This endpoint is ideal for applications requiring flexible response delivery.
            Use streaming mode for real-time interfaces and non-streaming for batch processing.
        """
        try:
            # Use the stream parameter from the request, defaulting to True if not specified
            stream_mode = request.stream if request.stream is not None else True
            param = request.to_query_params(stream_mode)

            from fastapi.responses import StreamingResponse

            # Unified approach: always use aquery_llm for all cases
            result = await rag.aquery_llm(request.query, param=param)

            async def stream_generator():
                # Extract references and LLM response from unified result
                references = result.get("data", {}).get("references", [])
                llm_response = result.get("llm_response", {})

                # Enrich references with chunk content if requested
                if request.include_references and request.include_chunk_content:
                    data = result.get("data", {})
                    chunks = data.get("chunks", [])
                    # Create a mapping from reference_id to chunk content
                    ref_id_to_content = {}
                    for chunk in chunks:
                        ref_id = chunk.get("reference_id", "")
                        content = chunk.get("content", "")
                        if ref_id and content:
                            # Collect chunk content
                            ref_id_to_content.setdefault(ref_id, []).append(content)

                    # Add content to references
                    enriched_references = []
                    for ref in references:
                        ref_copy = ref.copy()
                        ref_id = ref.get("reference_id", "")
                        if ref_id in ref_id_to_content:
                            # Keep content as a list of chunks (one file may have multiple chunks)
                            ref_copy["content"] = ref_id_to_content[ref_id]
                        enriched_references.append(ref_copy)
                    references = enriched_references

                if llm_response.get("is_streaming"):
                    # Streaming mode: send references first, then stream response chunks
                    if request.include_references:
                        yield f"{json.dumps({'references': references})}\n"

                    response_stream = llm_response.get("response_iterator")
                    if response_stream:
                        try:
                            async for chunk in response_stream:
                                if chunk:  # Only send non-empty content
                                    yield f"{json.dumps({'response': chunk})}\n"
                        except Exception as e:
                            logger.error(f"Streaming error: {str(e)}")
                            yield f"{json.dumps({'error': str(e)})}\n"
                else:
                    # Non-streaming mode: send complete response in one message
                    response_content = llm_response.get("content", "")
                    if not response_content:
                        response_content = "No relevant context found for the query."

                    # Create complete response object
                    complete_response = {"response": response_content}
                    if request.include_references:
                        complete_response["references"] = references

                    yield f"{json.dumps(complete_response)}\n"

            return StreamingResponse(
                stream_generator(),
                media_type="application/x-ndjson",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "Content-Type": "application/x-ndjson",
                    "X-Accel-Buffering": "no",  # Ensure proper handling of streaming response when proxied by Nginx
                },
            )
        except Exception as e:
            logger.error(f"Error processing streaming query: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    @router.post(
        "/query/data",
        response_model=QueryDataResponse,
        dependencies=[Depends(combined_auth)],
        responses={
            200: {
                "description": "成功的数据检索响应，包含结构化的RAG数据",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {
                                "status": {
                                    "type": "string",
                                    "enum": ["success", "failure"],
                                    "description": "查询执行状态",
                                },
                                "message": {
                                    "type": "string",
                                    "description": "描述结果的状态消息",
                                },
                                "data": {
                                    "type": "object",
                                    "properties": {
                                        "entities": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "entity_name": {"type": "string"},
                                                    "entity_type": {"type": "string"},
                                                    "description": {"type": "string"},
                                                    "source_id": {"type": "string"},
                                                    "file_path": {"type": "string"},
                                                    "reference_id": {"type": "string"},
                                                },
                                            },
                                            "description": "从知识图谱检索的实体",
                                        },
                                        "relationships": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "src_id": {"type": "string"},
                                                    "tgt_id": {"type": "string"},
                                                    "description": {"type": "string"},
                                                    "keywords": {"type": "string"},
                                                    "weight": {"type": "number"},
                                                    "source_id": {"type": "string"},
                                                    "file_path": {"type": "string"},
                                                    "reference_id": {"type": "string"},
                                                },
                                            },
                                            "description": "从知识图谱检索的关系",
                                        },
                                        "chunks": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "content": {"type": "string"},
                                                    "file_path": {"type": "string"},
                                                    "chunk_id": {"type": "string"},
                                                    "reference_id": {"type": "string"},
                                                },
                                            },
                                            "description": "从向量数据库检索的文本块",
                                        },
                                        "references": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "reference_id": {"type": "string"},
                                                    "file_path": {"type": "string"},
                                                },
                                            },
                                            "description": "用于引用目的的参考文献列表",
                                        },
                                    },
                                    "description": "包含实体、关系、块和参考文献的结构化检索数据",
                                },
                                "metadata": {
                                    "type": "object",
                                    "properties": {
                                        "query_mode": {"type": "string"},
                                        "keywords": {
                                            "type": "object",
                                            "properties": {
                                                "high_level": {
                                                    "type": "array",
                                                    "items": {"type": "string"},
                                                },
                                                "low_level": {
                                                    "type": "array",
                                                    "items": {"type": "string"},
                                                },
                                            },
                                        },
                                        "processing_info": {
                                            "type": "object",
                                            "properties": {
                                                "total_entities_found": {
                                                    "type": "integer"
                                                },
                                                "total_relations_found": {
                                                    "type": "integer"
                                                },
                                                "entities_after_truncation": {
                                                    "type": "integer"
                                                },
                                                "relations_after_truncation": {
                                                    "type": "integer"
                                                },
                                                "final_chunks_count": {
                                                    "type": "integer"
                                                },
                                            },
                                        },
                                    },
                                    "description": "包含模式、关键字和处理信息的查询元数据",
                                },
                            },
                            "required": ["status", "message", "data", "metadata"],
                        },
                        "examples": {
                            "successful_local_mode": {
                                "summary": "本地模式数据检索",
                                "description": "专注于特定实体的本地模式查询的结构化数据示例",
                                "value": {
                                    "status": "success",
                                    "message": "查询执行成功",
                                    "data": {
                                        "entities": [
                                            {
                                                "entity_name": "神经网络",
                                                "entity_type": "概念",
                                                "description": "受生物神经网络启发的计算模型",
                                                "source_id": "chunk-123",
                                                "file_path": "/documents/ai_basics.pdf",
                                                "reference_id": "1",
                                            }
                                        ],
                                        "relationships": [
                                            {
                                                "src_id": "神经网络",
                                                "tgt_id": "机器学习",
                                                "description": "神经网络是机器学习算法的一个子集",
                                                "keywords": "子集, 算法, 学习",
                                                "weight": 0.85,
                                                "source_id": "chunk-123",
                                                "file_path": "/documents/ai_basics.pdf",
                                                "reference_id": "1",
                                            }
                                        ],
                                        "chunks": [
                                            {
                                                "content": "神经网络是模仿生物神经网络工作方式的计算模型...",
                                                "file_path": "/documents/ai_basics.pdf",
                                                "chunk_id": "chunk-123",
                                                "reference_id": "1",
                                            }
                                        ],
                                        "references": [
                                            {
                                                "reference_id": "1",
                                                "file_path": "/documents/ai_basics.pdf",
                                            }
                                        ],
                                    },
                                    "metadata": {
                                        "query_mode": "local",
                                        "keywords": {
                                            "high_level": ["神经", "网络"],
                                            "low_level": [
                                                "计算",
                                                "模型",
                                                "算法",
                                            ],
                                        },
                                        "processing_info": {
                                            "total_entities_found": 5,
                                            "total_relations_found": 3,
                                            "entities_after_truncation": 1,
                                            "relations_after_truncation": 1,
                                            "final_chunks_count": 1,
                                        },
                                    },
                                },
                            },
                            "global_mode": {
                                "summary": "全局模式数据检索",
                                "description": "分析更广泛模式的全局模式查询的结构化数据示例",
                                "value": {
                                    "status": "success",
                                    "message": "查询执行成功",
                                    "data": {
                                        "entities": [],
                                        "relationships": [
                                            {
                                                "src_id": "人工智能",
                                                "tgt_id": "机器学习",
                                                "description": "AI将机器学习作为核心组件",
                                                "keywords": "包含, 组件, 领域",
                                                "weight": 0.92,
                                                "source_id": "chunk-456",
                                                "file_path": "/documents/ai_overview.pdf",
                                                "reference_id": "2",
                                            }
                                        ],
                                        "chunks": [],
                                        "references": [
                                            {
                                                "reference_id": "2",
                                                "file_path": "/documents/ai_overview.pdf",
                                            }
                                        ],
                                    },
                                    "metadata": {
                                        "query_mode": "global",
                                        "keywords": {
                                            "high_level": [
                                                "人工",
                                                "智能",
                                                "概览",
                                            ],
                                            "low_level": [],
                                        },
                                    },
                                },
                            },
                            "naive_mode": {
                                "summary": "朴素模式数据检索",
                                "description": "仅使用向量搜索的朴素模式查询的结构化数据示例",
                                "value": {
                                    "status": "success",
                                    "message": "查询执行成功",
                                    "data": {
                                        "entities": [],
                                        "relationships": [],
                                        "chunks": [
                                            {
                                                "content": "深度学习是机器学习的一个子集，使用具有多层的神经网络...",
                                                "file_path": "/documents/deep_learning.pdf",
                                                "chunk_id": "chunk-789",
                                                "reference_id": "3",
                                            }
                                        ],
                                        "references": [
                                            {
                                                "reference_id": "3",
                                                "file_path": "/documents/deep_learning.pdf",
                                            }
                                        ],
                                    },
                                    "metadata": {
                                        "query_mode": "naive",
                                        "keywords": {"high_level": [], "low_level": []},
                                    },
                                },
                            },
                        },
                    }
                },
            },
            400: {
                "description": "错误请求 - 无效的输入参数",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {"detail": {"type": "string"}},
                        },
                        "example": {
                            "detail": "查询文本长度必须至少为3个字符"
                        },
                    }
                },
            },
            500: {
                "description": "内部服务器错误 - 查询处理失败",
                "content": {
                    "application/json": {
                        "schema": {
                            "type": "object",
                            "properties": {"detail": {"type": "string"}},
                        },
                        "example": {
                            "detail": "处理数据查询失败：知识图谱不可用"
                        },
                    }
                },
            },
        },
    )
    async def query_data(request: QueryRequest):
        """
        Advanced data retrieval endpoint for structured RAG analysis.

        This endpoint provides raw retrieval results without LLM generation, perfect for:
        - **Data Analysis**: Examine what information would be used for RAG
        - **System Integration**: Get structured data for custom processing
        - **Debugging**: Understand retrieval behavior and quality
        - **Research**: Analyze knowledge graph structure and relationships

        **Key Features:**
        - No LLM generation - pure data retrieval
        - Complete structured output with entities, relationships, and chunks
        - Always includes references for citation
        - Detailed metadata about processing and keywords
        - Compatible with all query modes and parameters

        **Query Mode Behaviors:**
        - **local**: Returns entities and their direct relationships + related chunks
        - **global**: Returns relationship patterns across the knowledge graph
        - **hybrid**: Combines local and global retrieval strategies
        - **naive**: Returns only vector-retrieved text chunks (no knowledge graph)
        - **mix**: Integrates knowledge graph data with vector-retrieved chunks
        - **bypass**: Returns empty data arrays (used for direct LLM queries)

        **Data Structure:**
        - **entities**: Knowledge graph entities with descriptions and metadata
        - **relationships**: Connections between entities with weights and descriptions
        - **chunks**: Text segments from documents with source information
        - **references**: Citation information mapping reference IDs to file paths
        - **metadata**: Processing information, keywords, and query statistics

        **Usage Examples:**

        Analyze entity relationships:
        ```json
        {
            "query": "machine learning algorithms",
            "mode": "local",
            "top_k": 10
        }
        ```

        Explore global patterns:
        ```json
        {
            "query": "artificial intelligence trends",
            "mode": "global",
            "max_relation_tokens": 2000
        }
        ```

        Vector similarity search:
        ```json
        {
            "query": "neural network architectures",
            "mode": "naive",
            "chunk_top_k": 5
        }
        ```

        Bypass initial LLM call by providing high-level and low-level keywords:
        ```json
        {
            "query": "What is Retrieval-Augmented-Generation?",
            "hl_keywords": ["machine learning", "information retrieval", "natural language processing"],
            "ll_keywords": ["retrieval augmented generation", "RAG", "knowledge base"],
            "mode": "mix"
        }
        ```

        **Response Analysis:**
        - **Empty arrays**: Normal for certain modes (e.g., naive mode has no entities/relationships)
        - **Processing info**: Shows retrieval statistics and token usage
        - **Keywords**: High-level and low-level keywords extracted from query
        - **Reference mapping**: Links all data back to source documents

        Args:
            request (QueryRequest): The request object containing query parameters:
                - **query**: The search query to analyze (min 3 characters)
                - **mode**: Retrieval strategy affecting data types returned
                - **top_k**: Number of top entities/relationships to retrieve
                - **chunk_top_k**: Number of text chunks to retrieve
                - **max_entity_tokens**: Token limit for entity context
                - **max_relation_tokens**: Token limit for relationship context
                - **max_total_tokens**: Overall token budget for retrieval

        Returns:
            QueryDataResponse: Structured JSON response containing:
                - **status**: "success" or "failure"
                - **message**: Human-readable status description
                - **data**: Complete retrieval results with entities, relationships, chunks, references
                - **metadata**: Query processing information and statistics

        Raises:
            HTTPException:
                - 400: Invalid input parameters (e.g., query too short, invalid mode)
                - 500: Internal processing error (e.g., knowledge graph unavailable)

        Note:
            This endpoint always includes references regardless of the include_references parameter,
            as structured data analysis typically requires source attribution.
        """
        try:
            param = request.to_query_params(False)  # No streaming for data endpoint
            response = await rag.aquery_data(request.query, param=param)

            # aquery_data returns the new format with status, message, data, and metadata
            if isinstance(response, dict):
                return QueryDataResponse(**response)
            else:
                # Handle unexpected response format
                return QueryDataResponse(
                    status="failure",
                    message="Invalid response type",
                    data={},
                )
        except Exception as e:
            logger.error(f"Error processing data query: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))

    return router
