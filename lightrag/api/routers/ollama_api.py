from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Type
from lightrag.utils import logger
import time
import json
import re
from enum import Enum
from fastapi.responses import StreamingResponse
import asyncio
from lightrag import LightRAG, QueryParam
from lightrag.utils import TiktokenTokenizer
from lightrag.api.utils_api import get_combined_auth_dependency
from fastapi import Depends


# query mode according to query prefix (bypass is not LightRAG quer mode)
class SearchMode(str, Enum):
    naive = "naive"
    local = "local"
    global_ = "global"
    hybrid = "hybrid"
    mix = "mix"
    bypass = "bypass"
    context = "context"


class OllamaMessage(BaseModel):
    """Ollama消息格式"""
    role: str
    content: str
    images: Optional[List[str]] = None


class OllamaChatRequest(BaseModel):
    """Ollama聊天请求"""
    model: str
    messages: List[OllamaMessage]
    stream: bool = True
    options: Optional[Dict[str, Any]] = None
    system: Optional[str] = None


class OllamaChatResponse(BaseModel):
    """Ollama聊天响应"""
    model: str
    created_at: str
    message: OllamaMessage
    done: bool


class OllamaGenerateRequest(BaseModel):
    """Ollama生成请求"""
    model: str
    prompt: str
    system: Optional[str] = None
    stream: bool = False
    options: Optional[Dict[str, Any]] = None


class OllamaGenerateResponse(BaseModel):
    """Ollama生成响应"""
    model: str
    created_at: str
    response: str
    done: bool
    context: Optional[List[int]]
    total_duration: Optional[int]
    load_duration: Optional[int]
    prompt_eval_count: Optional[int]
    prompt_eval_duration: Optional[int]
    eval_count: Optional[int]
    eval_duration: Optional[int]


class OllamaVersionResponse(BaseModel):
    """Ollama版本响应"""
    version: str


class OllamaModelDetails(BaseModel):
    """Ollama模型详情"""
    parent_model: str
    format: str
    family: str
    families: List[str]
    parameter_size: str
    quantization_level: str


class OllamaModel(BaseModel):
    """Ollama模型"""
    name: str
    model: str
    size: int
    digest: str
    modified_at: str
    details: OllamaModelDetails


class OllamaTagResponse(BaseModel):
    """Ollama标签响应"""
    models: List[OllamaModel]


class OllamaRunningModelDetails(BaseModel):
    """Ollama运行中模型详情"""
    parent_model: str
    format: str
    family: str
    families: List[str]
    parameter_size: str
    quantization_level: str


class OllamaRunningModel(BaseModel):
    """Ollama运行中模型"""
    name: str
    model: str
    size: int
    digest: str
    details: OllamaRunningModelDetails
    expires_at: str
    size_vram: int


class OllamaPsResponse(BaseModel):
    """Ollama进程响应"""
    models: List[OllamaRunningModel]


async def parse_request_body(
    request: Request, model_class: Type[BaseModel]
) -> BaseModel:
    """
    根据Content-Type头解析请求体。
    支持application/json和application/octet-stream。

    参数:
        request: FastAPI请求对象
        model_class: 要解析请求的Pydantic模型类

    返回:
        提供的model_class的一个实例
    """
    content_type = request.headers.get("content-type", "").lower()

    try:
        if content_type.startswith("application/json"):
            # FastAPI已经为我们处理了JSON解析
            body = await request.json()
        elif content_type.startswith("application/octet-stream"):
            # 手动将octet-stream解析为JSON
            body_bytes = await request.body()
            body = json.loads(body_bytes.decode("utf-8"))
        else:
            # 尝试将任何其他内容类型解析为JSON
            body_bytes = await request.body()
            body = json.loads(body_bytes.decode("utf-8"))

        # 创建模型的实例
        return model_class(**body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="请求体中包含无效的JSON")
    except Exception as e:
        raise HTTPException(
            status_code=400, detail=f"解析请求体时出错: {str(e)}"
        )


def estimate_tokens(text: str) -> int:
    """使用tiktoken估算文本中的令牌数"""
    tokens = TiktokenTokenizer().encode(text)
    return len(tokens)


def parse_query_mode(query: str) -> tuple[str, SearchMode, bool, Optional[str]]:
    """解析查询前缀以确定搜索模式
    返回元组(cleaned_query, search_mode, only_need_context, user_prompt)

    示例:
    - "/local[使用mermaid格式绘制图表] 查询字符串" -> (cleaned_query, SearchMode.local, False, "使用mermaid格式绘制图表")
    - "/[使用mermaid格式绘制图表] 查询字符串" -> (cleaned_query, SearchMode.hybrid, False, "使用mermaid格式绘制图表")
    - "/local  查询字符串" -> (cleaned_query, SearchMode.local, False, None)
    """
    # 初始化user_prompt为None
    user_prompt = None

    # 首先检查是否有方括号格式的用户提示
    bracket_pattern = r"^/([a-z]*)\[(.*?)\](.*)"
    bracket_match = re.match(bracket_pattern, query)

    if bracket_match:
        mode_prefix = bracket_match.group(1)
        user_prompt = bracket_match.group(2)
        remaining_query = bracket_match.group(3).lstrip()

        # 重新构造查询，移除方括号部分
        query = f"/{mode_prefix} {remaining_query}".strip()

    # 统一处理模式和only_need_context的确定
    mode_map = {
        "/local ": (SearchMode.local, False),
        "/global ": (
            SearchMode.global_,
            False,
        ),  # global_被使用是因为'global'是Python关键字
        "/naive ": (SearchMode.naive, False),
        "/hybrid ": (SearchMode.hybrid, False),
        "/mix ": (SearchMode.mix, False),
        "/bypass ": (SearchMode.bypass, False),
        "/context": (
            SearchMode.mix,
            True,
        ),
        "/localcontext": (SearchMode.local, True),
        "/globalcontext": (SearchMode.global_, True),
        "/hybridcontext": (SearchMode.hybrid, True),
        "/naivecontext": (SearchMode.naive, True),
        "/mixcontext": (SearchMode.mix, True),
    }

    for prefix, (mode, only_need_context) in mode_map.items():
        if query.startswith(prefix):
            # 移除前缀和前导空格后
            cleaned_query = query[len(prefix) :].lstrip()
            return cleaned_query, mode, only_need_context, user_prompt

    return query, SearchMode.mix, False, user_prompt


class OllamaAPI:
    def __init__(self, rag: LightRAG, top_k: int = 60, api_key: Optional[str] = None):
        self.rag = rag
        self.ollama_server_infos = rag.ollama_server_infos
        self.top_k = top_k
        self.api_key = api_key
        self.router = APIRouter(tags=["Ollama兼容接口"])
        self.setup_routes()

    def setup_routes(self):
        # 为Ollama API路由创建组合认证依赖
        combined_auth = get_combined_auth_dependency(self.api_key)

        @self.router.get("/version", dependencies=[Depends(combined_auth)])
        async def get_version():
            """获取Ollama版本信息"""
            return OllamaVersionResponse(version="0.9.3")

        @self.router.get("/tags", dependencies=[Depends(combined_auth)])
        async def get_tags():
            """返回可用模型，充当Ollama服务器"""
            return OllamaTagResponse(
                models=[
                    {
                        "name": self.ollama_server_infos.LIGHTRAG_MODEL,
                        "model": self.ollama_server_infos.LIGHTRAG_MODEL,
                        "modified_at": self.ollama_server_infos.LIGHTRAG_CREATED_AT,
                        "size": self.ollama_server_infos.LIGHTRAG_SIZE,
                        "digest": self.ollama_server_infos.LIGHTRAG_DIGEST,
                        "details": {
                            "parent_model": "",
                            "format": "gguf",
                            "family": self.ollama_server_infos.LIGHTRAG_NAME,
                            "families": [self.ollama_server_infos.LIGHTRAG_NAME],
                            "parameter_size": "13B",
                            "quantization_level": "Q4_0",
                        },
                    }
                ]
            )

        @self.router.get("/ps", dependencies=[Depends(combined_auth)])
        async def get_running_models():
            """列出运行中的模型 - 返回当前运行的模型"""
            return OllamaPsResponse(
                models=[
                    {
                        "name": self.ollama_server_infos.LIGHTRAG_MODEL,
                        "model": self.ollama_server_infos.LIGHTRAG_MODEL,
                        "size": self.ollama_server_infos.LIGHTRAG_SIZE,
                        "digest": self.ollama_server_infos.LIGHTRAG_DIGEST,
                        "details": {
                            "parent_model": "",
                            "format": "gguf",
                            "family": "llama",
                            "families": ["llama"],
                            "parameter_size": "7.2B",
                            "quantization_level": "Q4_0",
                        },
                        "expires_at": "2050-12-31T14:38:31.83753-07:00",
                        "size_vram": self.ollama_server_infos.LIGHTRAG_SIZE,
                    }
                ]
            )

        @self.router.post(
            "/generate", dependencies=[Depends(combined_auth)], include_in_schema=True
        )
        async def generate(raw_request: Request):
            """处理生成完成请求，充当Ollama模型
            为了兼容性目的，请求不会由LightRAG处理，
            并将由底层LLM模型处理。
            支持application/json和application/octet-stream内容类型。
            """
            try:
                # 手动解析请求体
                request = await parse_request_body(raw_request, OllamaGenerateRequest)

                query = request.prompt
                start_time = time.time_ns()
                prompt_tokens = estimate_tokens(query)

                if request.system:
                    self.rag.llm_model_kwargs["system_prompt"] = request.system

                if request.stream:
                    response = await self.rag.llm_model_func(
                        query, stream=True, **self.rag.llm_model_kwargs
                    )

                    async def stream_generator():
                        first_chunk_time = None
                        last_chunk_time = time.time_ns()
                        total_response = ""

                        # 确保响应是一个异步生成器
                        if isinstance(response, str):
                            # 如果是字符串，则分两部分发送
                            first_chunk_time = start_time
                            last_chunk_time = time.time_ns()
                            total_response = response

                            data = {
                                "model": self.ollama_server_infos.LIGHTRAG_MODEL,
                                "created_at": self.ollama_server_infos.LIGHTRAG_CREATED_AT,
                                "response": response,
                                "done": False,
                            }
                            yield f"{json.dumps(data, ensure_ascii=False)}\n"

                            completion_tokens = estimate_tokens(total_response)
                            total_time = last_chunk_time - start_time
                            prompt_eval_time = first_chunk_time - start_time
                            eval_time = last_chunk_time - first_chunk_time

                            data = {
                                "model": self.ollama_server_infos.LIGHTRAG_MODEL,
                                "created_at": self.ollama_server_infos.LIGHTRAG_CREATED_AT,
                                "response": "",
                                "done": True,
                                "done_reason": "stop",
                                "context": [],
                                "total_duration": total_time,
                                "load_duration": 0,
                                "prompt_eval_count": prompt_tokens,
                                "prompt_eval_duration": prompt_eval_time,
                                "eval_count": completion_tokens,
                                "eval_duration": eval_time,
                            }
                            yield f"{json.dumps(data, ensure_ascii=False)}\n"
                        else:
                            try:
                                async for chunk in response:
                                    if chunk:
                                        if first_chunk_time is None:
                                            first_chunk_time = time.time_ns()

                                        last_chunk_time = time.time_ns()

                                        total_response += chunk
                                        data = {
                                            "model": self.ollama_server_infos.LIGHTRAG_MODEL,
                                            "created_at": self.ollama_server_infos.LIGHTRAG_CREATED_AT,
                                            "response": chunk,
                                            "done": False,
                                        }
                                        yield f"{json.dumps(data, ensure_ascii=False)}\n"
                            except (asyncio.CancelledError, Exception) as e:
                                error_msg = str(e)
                                if isinstance(e, asyncio.CancelledError):
                                    error_msg = "流被服务器取消"
                                else:
                                    error_msg = f"提供程序错误: {error_msg}"

                                logger.error(f"流错误: {error_msg}")

                                # 向客户端发送错误消息
                                error_data = {
                                    "model": self.ollama_server_infos.LIGHTRAG_MODEL,
                                    "created_at": self.ollama_server_infos.LIGHTRAG_CREATED_AT,
                                    "response": f"\n\n错误: {error_msg}",
                                    "error": f"\n\n错误: {error_msg}",
                                    "done": False,
                                }
                                yield f"{json.dumps(error_data, ensure_ascii=False)}\n"

                                # 发送最终消息以关闭流
                                final_data = {
                                    "model": self.ollama_server_infos.LIGHTRAG_MODEL,
                                    "created_at": self.ollama_server_infos.LIGHTRAG_CREATED_AT,
                                    "response": "",
                                    "done": True,
                                }
                                yield f"{json.dumps(final_data, ensure_ascii=False)}\n"
                                return
                            if first_chunk_time is None:
                                first_chunk_time = start_time
                            completion_tokens = estimate_tokens(total_response)
                            total_time = last_chunk_time - start_time
                            prompt_eval_time = first_chunk_time - start_time
                            eval_time = last_chunk_time - first_chunk_time

                            data = {
                                "model": self.ollama_server_infos.LIGHTRAG_MODEL,
                                "created_at": self.ollama_server_infos.LIGHTRAG_CREATED_AT,
                                "response": "",
                                "done": True,
                                "done_reason": "stop",
                                "context": [],
                                "total_duration": total_time,
                                "load_duration": 0,
                                "prompt_eval_count": prompt_tokens,
                                "prompt_eval_duration": prompt_eval_time,
                                "eval_count": completion_tokens,
                                "eval_duration": eval_time,
                            }
                            yield f"{json.dumps(data, ensure_ascii=False)}\n"
                            return

                    return StreamingResponse(
                        stream_generator(),
                        media_type="application/x-ndjson",
                        headers={
                            "Cache-Control": "no-cache",
                            "Connection": "keep-alive",
                            "Content-Type": "application/x-ndjson",
                            "X-Accel-Buffering": "no",  # 确保Nginx代理中正确处理流式响应
                        },
                    )
                else:
                    first_chunk_time = time.time_ns()
                    response_text = await self.rag.llm_model_func(
                        query, stream=False, **self.rag.llm_model_kwargs
                    )
                    last_chunk_time = time.time_ns()

                    if not response_text:
                        response_text = "未生成响应"

                    completion_tokens = estimate_tokens(str(response_text))
                    total_time = last_chunk_time - start_time
                    prompt_eval_time = first_chunk_time - start_time
                    eval_time = last_chunk_time - first_chunk_time

                    return {
                        "model": self.ollama_server_infos.LIGHTRAG_MODEL,
                        "created_at": self.ollama_server_infos.LIGHTRAG_CREATED_AT,
                        "response": str(response_text),
                        "done": True,
                        "done_reason": "stop",
                        "context": [],
                        "total_duration": total_time,
                        "load_duration": 0,
                        "prompt_eval_count": prompt_tokens,
                        "prompt_eval_duration": prompt_eval_time,
                        "eval_count": completion_tokens,
                        "eval_duration": eval_time,
                    }
            except Exception as e:
                logger.error(f"Ollama生成错误: {str(e)}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))

        @self.router.post(
            "/chat", dependencies=[Depends(combined_auth)], include_in_schema=True
        )
        async def chat(raw_request: Request):
            """通过充当Ollama模型来处理聊天完成请求。
            通过基于查询前缀选择查询模式，将用户查询路由到LightRAG。
            检测并直接转发OpenWebUI会话相关请求（用于元数据生成任务）到LLM。
            支持application/json和application/octet-stream内容类型。
            """
            try:
                # 手动解析请求体
                request = await parse_request_body(raw_request, OllamaChatRequest)

                # 获取所有消息
                messages = request.messages
                if not messages:
                    raise HTTPException(status_code=400, detail="未提供消息")

                # 验证最后一条消息来自用户
                if messages[-1].role != "user":
                    raise HTTPException(
                        status_code=400, detail="最后一条消息必须来自用户角色"
                    )

                # 将最后一条消息作为查询，之前的消息作为历史记录
                query = messages[-1].content
                # 将OllamaMessage对象转换为字典
                conversation_history = [
                    {"role": msg.role, "content": msg.content} for msg in messages[:-1]
                ]

                # 检查查询前缀
                cleaned_query, mode, only_need_context, user_prompt = parse_query_mode(
                    query
                )

                start_time = time.time_ns()
                prompt_tokens = estimate_tokens(cleaned_query)

                param_dict = {
                    "mode": mode.value,
                    "stream": request.stream,
                    "only_need_context": only_need_context,
                    "conversation_history": conversation_history,
                    "top_k": self.top_k,
                }

                # 添加user_prompt到param_dict
                if user_prompt is not None:
                    param_dict["user_prompt"] = user_prompt

                query_param = QueryParam(**param_dict)

                if request.stream:
                    # 确定请求是否以前缀"/bypass"开头
                    if mode == SearchMode.bypass:
                        if request.system:
                            self.rag.llm_model_kwargs["system_prompt"] = request.system
                        response = await self.rag.llm_model_func(
                            cleaned_query,
                            stream=True,
                            history_messages=conversation_history,
                            **self.rag.llm_model_kwargs,
                        )
                    else:
                        response = await self.rag.aquery(
                            cleaned_query, param=query_param
                        )

                    async def stream_generator():
                        first_chunk_time = None
                        last_chunk_time = time.time_ns()
                        total_response = ""

                        # 确保响应是一个异步生成器
                        if isinstance(response, str):
                            # 如果是字符串，则分两部分发送
                            first_chunk_time = start_time
                            last_chunk_time = time.time_ns()
                            total_response = response

                            data = {
                                "model": self.ollama_server_infos.LIGHTRAG_MODEL,
                                "created_at": self.ollama_server_infos.LIGHTRAG_CREATED_AT,
                                "message": {
                                    "role": "assistant",
                                    "content": response,
                                    "images": None,
                                },
                                "done": False,
                            }
                            yield f"{json.dumps(data, ensure_ascii=False)}\n"

                            completion_tokens = estimate_tokens(total_response)
                            total_time = last_chunk_time - start_time
                            prompt_eval_time = first_chunk_time - start_time
                            eval_time = last_chunk_time - first_chunk_time

                            data = {
                                "model": self.ollama_server_infos.LIGHTRAG_MODEL,
                                "created_at": self.ollama_server_infos.LIGHTRAG_CREATED_AT,
                                "message": {
                                    "role": "assistant",
                                    "content": "",
                                    "images": None,
                                },
                                "done_reason": "stop",
                                "done": True,
                                "total_duration": total_time,
                                "load_duration": 0,
                                "prompt_eval_count": prompt_tokens,
                                "prompt_eval_duration": prompt_eval_time,
                                "eval_count": completion_tokens,
                                "eval_duration": eval_time,
                            }
                            yield f"{json.dumps(data, ensure_ascii=False)}\n"
                        else:
                            try:
                                async for chunk in response:
                                    if chunk:
                                        if first_chunk_time is None:
                                            first_chunk_time = time.time_ns()

                                        last_chunk_time = time.time_ns()

                                        total_response += chunk
                                        data = {
                                            "model": self.ollama_server_infos.LIGHTRAG_MODEL,
                                            "created_at": self.ollama_server_infos.LIGHTRAG_CREATED_AT,
                                            "message": {
                                                "role": "assistant",
                                                "content": chunk,
                                                "images": None,
                                            },
                                            "done": False,
                                        }
                                        yield f"{json.dumps(data, ensure_ascii=False)}\n"
                            except (asyncio.CancelledError, Exception) as e:
                                error_msg = str(e)
                                if isinstance(e, asyncio.CancelledError):
                                    error_msg = "流被服务器取消"
                                else:
                                    error_msg = f"提供程序错误: {error_msg}"

                                logger.error(f"流错误: {error_msg}")

                                # 向客户端发送错误消息
                                error_data = {
                                    "model": self.ollama_server_infos.LIGHTRAG_MODEL,
                                    "created_at": self.ollama_server_infos.LIGHTRAG_CREATED_AT,
                                    "message": {
                                        "role": "assistant",
                                        "content": f"\n\n错误: {error_msg}",
                                        "images": None,
                                    },
                                    "error": f"\n\n错误: {error_msg}",
                                    "done": False,
                                }
                                yield f"{json.dumps(error_data, ensure_ascii=False)}\n"

                                # 发送最终消息以关闭流
                                final_data = {
                                    "model": self.ollama_server_infos.LIGHTRAG_MODEL,
                                    "created_at": self.ollama_server_infos.LIGHTRAG_CREATED_AT,
                                    "message": {
                                        "role": "assistant",
                                        "content": "",
                                        "images": None,
                                    },
                                    "done": True,
                                }
                                yield f"{json.dumps(final_data, ensure_ascii=False)}\n"
                                return

                            if first_chunk_time is None:
                                first_chunk_time = start_time
                            completion_tokens = estimate_tokens(total_response)
                            total_time = last_chunk_time - start_time
                            prompt_eval_time = first_chunk_time - start_time
                            eval_time = last_chunk_time - first_chunk_time

                            data = {
                                "model": self.ollama_server_infos.LIGHTRAG_MODEL,
                                "created_at": self.ollama_server_infos.LIGHTRAG_CREATED_AT,
                                "message": {
                                    "role": "assistant",
                                    "content": "",
                                    "images": None,
                                },
                                "done_reason": "stop",
                                "done": True,
                                "total_duration": total_time,
                                "load_duration": 0,
                                "prompt_eval_count": prompt_tokens,
                                "prompt_eval_duration": prompt_eval_time,
                                "eval_count": completion_tokens,
                                "eval_duration": eval_time,
                            }
                            yield f"{json.dumps(data, ensure_ascii=False)}\n"

                    return StreamingResponse(
                        stream_generator(),
                        media_type="application/x-ndjson",
                        headers={
                            "Cache-Control": "no-cache",
                            "Connection": "keep-alive",
                            "Content-Type": "application/x-ndjson",
                            "X-Accel-Buffering": "no",  # 确保Nginx代理中正确处理流式响应
                        },
                    )
                else:
                    first_chunk_time = time.time_ns()

                    # 确定请求是否以前缀"/bypass"开头或来自Open WebUI的会话标题和会话关键词生成任务
                    match_result = re.search(
                        r"\n<chat_history>\nUSER:", cleaned_query, re.MULTILINE
                    )
                    if match_result or mode == SearchMode.bypass:
                        if request.system:
                            self.rag.llm_model_kwargs["system_prompt"] = request.system

                        response_text = await self.rag.llm_model_func(
                            cleaned_query,
                            stream=False,
                            history_messages=conversation_history,
                            **self.rag.llm_model_kwargs,
                        )
                    else:
                        response_text = await self.rag.aquery(
                            cleaned_query, param=query_param
                        )

                    last_chunk_time = time.time_ns()

                    if not response_text:
                        response_text = "未生成响应"

                    completion_tokens = estimate_tokens(str(response_text))
                    total_time = last_chunk_time - start_time
                    prompt_eval_time = first_chunk_time - start_time
                    eval_time = last_chunk_time - first_chunk_time

                    return {
                        "model": self.ollama_server_infos.LIGHTRAG_MODEL,
                        "created_at": self.ollama_server_infos.LIGHTRAG_CREATED_AT,
                        "message": {
                            "role": "assistant",
                            "content": str(response_text),
                            "images": None,
                        },
                        "done_reason": "stop",
                        "done": True,
                        "total_duration": total_time,
                        "load_duration": 0,
                        "prompt_eval_count": prompt_tokens,
                        "prompt_eval_duration": prompt_eval_time,
                        "eval_count": completion_tokens,
                        "eval_duration": eval_time,
                    }
            except Exception as e:
                logger.error(f"Ollama聊天错误: {str(e)}", exc_info=True)
                raise HTTPException(status_code=500, detail=str(e))
