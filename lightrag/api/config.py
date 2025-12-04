"""
LightRAG API的配置。
"""

import os
import argparse
import logging
from dotenv import load_dotenv
from lightrag.utils import get_env_value
from lightrag.llm.binding_options import (
    GeminiEmbeddingOptions,
    GeminiLLMOptions,
    OllamaEmbeddingOptions,
    OllamaLLMOptions,
    OpenAILLMOptions,
)
from lightrag.base import OllamaServerInfos
import sys

from lightrag.constants import (
    DEFAULT_WOKERS,
    DEFAULT_TIMEOUT,
    DEFAULT_TOP_K,
    DEFAULT_CHUNK_TOP_K,
    DEFAULT_HISTORY_TURNS,
    DEFAULT_MAX_ENTITY_TOKENS,
    DEFAULT_MAX_RELATION_TOKENS,
    DEFAULT_MAX_TOTAL_TOKENS,
    DEFAULT_COSINE_THRESHOLD,
    DEFAULT_RELATED_CHUNK_NUMBER,
    DEFAULT_MIN_RERANK_SCORE,
    DEFAULT_FORCE_LLM_SUMMARY_ON_MERGE,
    DEFAULT_MAX_ASYNC,
    DEFAULT_SUMMARY_MAX_TOKENS,
    DEFAULT_SUMMARY_LENGTH_RECOMMENDED,
    DEFAULT_SUMMARY_CONTEXT_SIZE,
    DEFAULT_SUMMARY_LANGUAGE,
    DEFAULT_EMBEDDING_FUNC_MAX_ASYNC,
    DEFAULT_EMBEDDING_BATCH_NUM,
    DEFAULT_OLLAMA_MODEL_NAME,
    DEFAULT_OLLAMA_MODEL_TAG,
    DEFAULT_RERANK_BINDING,
    DEFAULT_ENTITY_TYPES,
)

# 使用当前文件夹中的.env文件
# 允许为每个lightrag实例使用不同的.env文件
# 操作系统环境变量优先于.env文件
load_dotenv(dotenv_path=".env", override=False)


ollama_server_infos = OllamaServerInfos()


class DefaultRAGStorageConfig:
    KV_STORAGE = "JsonKVStorage"
    VECTOR_STORAGE = "NanoVectorDBStorage"
    GRAPH_STORAGE = "NetworkXStorage"
    DOC_STATUS_STORAGE = "JsonDocStatusStorage"


def get_default_host(binding_type: str) -> str:
    default_hosts = {
        "ollama": os.getenv("LLM_BINDING_HOST", "http://localhost:11434"),
        "lollms": os.getenv("LLM_BINDING_HOST", "http://localhost:9600"),
        "azure_openai": os.getenv("AZURE_OPENAI_ENDPOINT", "https://api.openai.com/v1"),
        "openai": os.getenv("LLM_BINDING_HOST", "https://api.openai.com/v1"),
        "gemini": os.getenv(
            "LLM_BINDING_HOST", "https://generativelanguage.googleapis.com"
        ),
    }
    return default_hosts.get(
        binding_type, os.getenv("LLM_BINDING_HOST", "http://localhost:11434")
    )  # 如果未知则回退到ollama


def parse_args() -> argparse.Namespace:
    """
    解析命令行参数，支持环境变量回退

    参数:
        is_uvicorn_mode: 是否在uvicorn模式下运行

    返回:
        argparse.Namespace: 已解析的参数
    """

    parser = argparse.ArgumentParser(description="LightRAG API服务器")

    # 服务器配置
    parser.add_argument(
        "--host",
        default=get_env_value("HOST", "0.0.0.0"),
        help="服务器主机 (默认: 从环境变量或0.0.0.0获取)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=get_env_value("PORT", 9621, int),
        help="服务器端口 (默认: 从环境变量或9621获取)",
    )

    # 目录配置
    parser.add_argument(
        "--working-dir",
        default=get_env_value("WORKING_DIR", "./rag_storage"),
        help="RAG存储的工作目录 (默认: 从环境变量或./rag_storage获取)",
    )
    parser.add_argument(
        "--input-dir",
        default=get_env_value("INPUT_DIR", "./inputs"),
        help="包含输入文档的目录 (默认: 从环境变量或./inputs获取)",
    )

    parser.add_argument(
        "--timeout",
        default=get_env_value("TIMEOUT", DEFAULT_TIMEOUT, int, special_none=True),
        type=int,
        help="超时时间（秒）（当使用慢速AI时有用）。使用None表示无限超时",
    )

    # RAG配置
    parser.add_argument(
        "--max-async",
        type=int,
        default=get_env_value("MAX_ASYNC", DEFAULT_MAX_ASYNC, int),
        help=f"最大异步操作数 (默认: 从环境变量或{DEFAULT_MAX_ASYNC}获取)",
    )
    parser.add_argument(
        "--summary-max-tokens",
        type=int,
        default=get_env_value("SUMMARY_MAX_TOKENS", DEFAULT_SUMMARY_MAX_TOKENS, int),
        help=f"实体/关系摘要的最大令牌大小(默认: 从环境变量或{DEFAULT_SUMMARY_MAX_TOKENS}获取)",
    )
    parser.add_argument(
        "--summary-context-size",
        type=int,
        default=get_env_value(
            "SUMMARY_CONTEXT_SIZE", DEFAULT_SUMMARY_CONTEXT_SIZE, int
        ),
        help=f"LLM摘要上下文大小 (默认: 从环境变量或{DEFAULT_SUMMARY_CONTEXT_SIZE}获取)",
    )
    parser.add_argument(
        "--summary-length-recommended",
        type=int,
        default=get_env_value(
            "SUMMARY_LENGTH_RECOMMENDED", DEFAULT_SUMMARY_LENGTH_RECOMMENDED, int
        ),
        help=f"LLM摘要推荐长度 (默认: 从环境变量或{DEFAULT_SUMMARY_LENGTH_RECOMMENDED}获取)",
    )

    # 日志配置
    parser.add_argument(
        "--log-level",
        default=get_env_value("LOG_LEVEL", "INFO"),
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="日志级别 (默认: 从环境变量或INFO获取)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        default=get_env_value("VERBOSE", False, bool),
        help="启用详细调试输出(仅对DEBUG日志级别有效)",
    )

    parser.add_argument(
        "--key",
        type=str,
        default=get_env_value("LIGHTRAG_API_KEY", None),
        help="用于认证的API密钥。这可以保护lightrag服务器免受未经授权的访问",
    )

    # 可选的https参数
    parser.add_argument(
        "--ssl",
        action="store_true",
        default=get_env_value("SSL", False, bool),
        help="启用HTTPS (默认: 从环境变量或False获取)",
    )
    parser.add_argument(
        "--ssl-certfile",
        default=get_env_value("SSL_CERTFILE", None),
        help="SSL证书文件的路径 (如果启用--ssl则必需)",
    )
    parser.add_argument(
        "--ssl-keyfile",
        default=get_env_value("SSL_KEYFILE", None),
        help="SSL私钥文件的路径 (如果启用--ssl则必需)",
    )

    # Ollama模型配置
    parser.add_argument(
        "--simulated-model-name",
        type=str,
        default=get_env_value("OLLAMA_EMULATING_MODEL_NAME", DEFAULT_OLLAMA_MODEL_NAME),
        help="模拟的Ollama模型名称 (默认: 从环境变量或lightrag获取)",
    )

    parser.add_argument(
        "--simulated-model-tag",
        type=str,
        default=get_env_value("OLLAMA_EMULATING_MODEL_TAG", DEFAULT_OLLAMA_MODEL_TAG),
        help="模拟的Ollama模型标签 (默认: 从环境变量或latest获取)",
    )

    # 命名空间
    parser.add_argument(
        "--workspace",
        type=str,
        default=get_env_value("WORKSPACE", ""),
        help="所有存储的默认工作区",
    )

    # 服务器工作进程配置
    parser.add_argument(
        "--workers",
        type=int,
        default=get_env_value("WORKERS", DEFAULT_WOKERS, int),
        help="工作进程数 (默认: 从环境变量或1获取)",
    )

    # LLM和嵌入绑定
    parser.add_argument(
        "--llm-binding",
        type=str,
        default=get_env_value("LLM_BINDING", "ollama"),
        choices=[
            "lollms",
            "ollama",
            "openai",
            "openai-ollama",
            "azure_openai",
            "aws_bedrock",
            "gemini",
        ],
        help="LLM绑定类型 (默认: 从环境变量或ollama获取)",
    )
    parser.add_argument(
        "--embedding-binding",
        type=str,
        default=get_env_value("EMBEDDING_BINDING", "ollama"),
        choices=[
            "lollms",
            "ollama",
            "openai",
            "azure_openai",
            "aws_bedrock",
            "jina",
            "gemini",
        ],
        help="嵌入绑定类型 (默认: 从环境变量或ollama获取)",
    )
    parser.add_argument(
        "--rerank-binding",
        type=str,
        default=get_env_value("RERANK_BINDING", DEFAULT_RERANK_BINDING),
        choices=["null", "cohere", "jina", "aliyun"],
        help=f"重排序绑定类型 (默认: 从环境变量或{DEFAULT_RERANK_BINDING}获取)",
    )

    # 文档加载引擎配置
    parser.add_argument(
        "--docling",
        action="store_true",
        default=False,
        help="启用DOCLING文档加载引擎 (默认: 从环境变量或DEFAULT获取)",
    )

    # 条件性添加在binding_options模块中定义的绑定选项
    # 这将为所有绑定选项添加命令行参数（例如，--ollama-embedding-num_ctx）
    # 和相应的环境变量（例如，OLLAMA_EMBEDDING_NUM_CTX）
    if "--llm-binding" in sys.argv:
        try:
            idx = sys.argv.index("--llm-binding")
            if idx + 1 < len(sys.argv) and sys.argv[idx + 1] == "ollama":
                OllamaLLMOptions.add_args(parser)
        except IndexError:
            pass
    elif os.environ.get("LLM_BINDING") == "ollama":
        OllamaLLMOptions.add_args(parser)

    if "--embedding-binding" in sys.argv:
        try:
            idx = sys.argv.index("--embedding-binding")
            if idx + 1 < len(sys.argv):
                if sys.argv[idx + 1] == "ollama":
                    OllamaEmbeddingOptions.add_args(parser)
                elif sys.argv[idx + 1] == "gemini":
                    GeminiEmbeddingOptions.add_args(parser)
        except IndexError:
            pass
    else:
        env_embedding_binding = os.environ.get("EMBEDDING_BINDING")
        if env_embedding_binding == "ollama":
            OllamaEmbeddingOptions.add_args(parser)
        elif env_embedding_binding == "gemini":
            GeminiEmbeddingOptions.add_args(parser)

    # 当llm-binding为openai或azure_openai时添加OpenAI LLM选项
    if "--llm-binding" in sys.argv:
        try:
            idx = sys.argv.index("--llm-binding")
            if idx + 1 < len(sys.argv) and sys.argv[idx + 1] in [
                "openai",
                "azure_openai",
            ]:
                OpenAILLMOptions.add_args(parser)
        except IndexError:
            pass
    elif os.environ.get("LLM_BINDING") in ["openai", "azure_openai"]:
        OpenAILLMOptions.add_args(parser)

    if "--llm-binding" in sys.argv:
        try:
            idx = sys.argv.index("--llm-binding")
            if idx + 1 < len(sys.argv) and sys.argv[idx + 1] == "gemini":
                GeminiLLMOptions.add_args(parser)
        except IndexError:
            pass
    elif os.environ.get("LLM_BINDING") == "gemini":
        GeminiLLMOptions.add_args(parser)

    args = parser.parse_args()

    # 将相对路径转换为绝对路径
    args.working_dir = os.path.abspath(args.working_dir)
    args.input_dir = os.path.abspath(args.input_dir)

    # 从环境变量注入存储配置
    args.kv_storage = get_env_value(
        "LIGHTRAG_KV_STORAGE", DefaultRAGStorageConfig.KV_STORAGE
    )
    args.doc_status_storage = get_env_value(
        "LIGHTRAG_DOC_STATUS_STORAGE", DefaultRAGStorageConfig.DOC_STATUS_STORAGE
    )
    args.graph_storage = get_env_value(
        "LIGHTRAG_GRAPH_STORAGE", DefaultRAGStorageConfig.GRAPH_STORAGE
    )
    args.vector_storage = get_env_value(
        "LIGHTRAG_VECTOR_STORAGE", DefaultRAGStorageConfig.VECTOR_STORAGE
    )

    # 从环境获取MAX_PARALLEL_INSERT
    args.max_parallel_insert = get_env_value("MAX_PARALLEL_INSERT", 2, int)

    # 从环境获取MAX_GRAPH_NODES
    args.max_graph_nodes = get_env_value("MAX_GRAPH_NODES", 1000, int)

    # 处理openai-ollama特殊情况
    if args.llm_binding == "openai-ollama":
        args.llm_binding = "openai"
        args.embedding_binding = "ollama"

    # Ollama ctx_num
    args.ollama_num_ctx = get_env_value("OLLAMA_NUM_CTX", 32768, int)

    args.llm_binding_host = get_env_value(
        "LLM_BINDING_HOST", get_default_host(args.llm_binding)
    )
    args.embedding_binding_host = get_env_value(
        "EMBEDDING_BINDING_HOST", get_default_host(args.embedding_binding)
    )
    args.llm_binding_api_key = get_env_value("LLM_BINDING_API_KEY", None)
    args.embedding_binding_api_key = get_env_value("EMBEDDING_BINDING_API_KEY", "")

    # 注入模型配置
    args.llm_model = get_env_value("LLM_MODEL", "mistral-nemo:latest")
    # EMBEDDING_MODEL默认为None - 每个绑定将使用自己的默认模型
    # 例如，OpenAI使用"text-embedding-3-small"，Jina使用"jina-embeddings-v4"
    args.embedding_model = get_env_value("EMBEDDING_MODEL", None, special_none=True)
    # EMBEDDING_DIM默认为None - 每个绑定将使用自己的默认维度
    # 通过wrap_embedding_func_with_attrs装饰器继承自提供者的默认值
    args.embedding_dim = get_env_value("EMBEDDING_DIM", None, int, special_none=True)
    args.embedding_send_dim = get_env_value("EMBEDDING_SEND_DIM", False, bool)

    # 注入块配置
    args.chunk_size = get_env_value("CHUNK_SIZE", 1200, int)
    args.chunk_overlap_size = get_env_value("CHUNK_OVERLAP_SIZE", 100, int)

    # 注入LLM缓存配置
    args.enable_llm_cache_for_extract = get_env_value(
        "ENABLE_LLM_CACHE_FOR_EXTRACT", True, bool
    )
    args.enable_llm_cache = get_env_value("ENABLE_LLM_CACHE", True, bool)

    # 设置document_loading_engine从--docling标志
    if args.docling:
        args.document_loading_engine = "DOCLING"
    else:
        args.document_loading_engine = get_env_value(
            "DOCUMENT_LOADING_ENGINE", "DEFAULT"
        )

    # PDF解密密码
    args.pdf_decrypt_password = get_env_value("PDF_DECRYPT_PASSWORD", None)

    # 添加之前直接读取的环境变量
    args.cors_origins = get_env_value("CORS_ORIGINS", "*")
    args.summary_language = get_env_value("SUMMARY_LANGUAGE", DEFAULT_SUMMARY_LANGUAGE)
    args.entity_types = get_env_value("ENTITY_TYPES", DEFAULT_ENTITY_TYPES, list)
    args.whitelist_paths = get_env_value("WHITELIST_PATHS", "/health,/api/*")

    # 用于JWT认证
    args.auth_accounts = get_env_value("AUTH_ACCOUNTS", "")
    args.token_secret = get_env_value("TOKEN_SECRET", "lightrag-jwt-default-secret")
    args.token_expire_hours = get_env_value("TOKEN_EXPIRE_HOURS", 48, int)
    args.guest_token_expire_hours = get_env_value("GUEST_TOKEN_EXPIRE_HOURS", 24, int)
    args.jwt_algorithm = get_env_value("JWT_ALGORITHM", "HS256")

    # 重排序模型配置
    args.rerank_model = get_env_value("RERANK_MODEL", None)
    args.rerank_binding_host = get_env_value("RERANK_BINDING_HOST", None)
    args.rerank_binding_api_key = get_env_value("RERANK_BINDING_API_KEY", None)
    # 注意：rerank_binding已经由argparse设置，无需从环境覆盖

    # 最小重排序分数配置
    args.min_rerank_score = get_env_value(
        "MIN_RERANK_SCORE", DEFAULT_MIN_RERANK_SCORE, float
    )

    # 查询配置
    args.history_turns = get_env_value("HISTORY_TURNS", DEFAULT_HISTORY_TURNS, int)
    args.top_k = get_env_value("TOP_K", DEFAULT_TOP_K, int)
    args.chunk_top_k = get_env_value("CHUNK_TOP_K", DEFAULT_CHUNK_TOP_K, int)
    args.max_entity_tokens = get_env_value(
        "MAX_ENTITY_TOKENS", DEFAULT_MAX_ENTITY_TOKENS, int
    )
    args.max_relation_tokens = get_env_value(
        "MAX_RELATION_TOKENS", DEFAULT_MAX_RELATION_TOKENS, int
    )
    args.max_total_tokens = get_env_value(
        "MAX_TOTAL_TOKENS", DEFAULT_MAX_TOTAL_TOKENS, int
    )
    args.cosine_threshold = get_env_value(
        "COSINE_THRESHOLD", DEFAULT_COSINE_THRESHOLD, float
    )
    args.related_chunk_number = get_env_value(
        "RELATED_CHUNK_NUMBER", DEFAULT_RELATED_CHUNK_NUMBER, int
    )

    # 为健康端点添加缺失的环境变量
    args.force_llm_summary_on_merge = get_env_value(
        "FORCE_LLM_SUMMARY_ON_MERGE", DEFAULT_FORCE_LLM_SUMMARY_ON_MERGE, int
    )
    args.embedding_func_max_async = get_env_value(
        "EMBEDDING_FUNC_MAX_ASYNC", DEFAULT_EMBEDDING_FUNC_MAX_ASYNC, int
    )
    args.embedding_batch_num = get_env_value(
        "EMBEDDING_BATCH_NUM", DEFAULT_EMBEDDING_BATCH_NUM, int
    )

    # 嵌入令牌限制配置
    args.embedding_token_limit = get_env_value(
        "EMBEDDING_TOKEN_LIMIT", None, int, special_none=True
    )

    ollama_server_infos.LIGHTRAG_NAME = args.simulated_model_name
    ollama_server_infos.LIGHTRAG_TAG = args.simulated_model_tag

    return args


def update_uvicorn_mode_config():
    # 如果在uvicorn模式下且workers > 1，则强制设置为1并记录警告
    if global_args.workers > 1:
        original_workers = global_args.workers
        global_args.workers = 1
        # 直接在此处记录警告
        logging.warning(
            f">> Forcing workers=1 in uvicorn mode(Ignoring workers={original_workers})"
        )


# 全局配置，延迟初始化
_global_args = None
_initialized = False


def initialize_config(args=None, force=False):
    """初始化全局配置

    该函数允许显式初始化配置，
    这对于程序化使用、测试或在其他应用程序中嵌入LightRAG很有用。

    参数:
        args: 已解析的argparse.Namespace或None以从sys.argv解析
        force: 即使已初始化也强制重新初始化

    返回:
        argparse.Namespace: 配置的参数

    示例:
        # 使用命令行参数（默认）
        initialize_config()

        # 使用自定义配置进行程序化设置
        custom_args = argparse.Namespace(
            host='localhost',
            port=8080,
            working_dir='./custom_rag',
            # ... 其他配置
        )
        initialize_config(custom_args)
    """
    global _global_args, _initialized

    if _initialized and not force:
        return _global_args

    _global_args = args if args is not None else parse_args()
    _initialized = True
    return _global_args


def get_config():
    """获取全局配置，如果需要则自动初始化

    返回:
        argparse.Namespace: 配置的参数
    """
    if not _initialized:
        initialize_config()
    return _global_args


class _GlobalArgsProxy:
    """代理对象，首次访问时自动初始化配置

    这保持了与现有代码的向后兼容性，
    同时允许对初始化时间进行程序化控制。
    """

    def __getattr__(self, name):
        if not _initialized:
            initialize_config()
        return getattr(_global_args, name)

    def __setattr__(self, name, value):
        if not _initialized:
            initialize_config()
        setattr(_global_args, name, value)

    def __repr__(self):
        if not _initialized:
            return "<GlobalArgsProxy: Not initialized>"
        return repr(_global_args)


# 创建代理实例以保持向后兼容性
# 现有代码如`from config import global_args`继续正常工作
# 代理将在首次属性访问时自动初始化
global_args = _GlobalArgsProxy()
