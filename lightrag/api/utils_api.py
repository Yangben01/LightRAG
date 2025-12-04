"""
LightRAG API的实用函数。
"""

import os
import argparse
from typing import Optional, List, Tuple
import sys
from ascii_colors import ASCIIColors
from lightrag.api import __api_version__ as api_version
from lightrag import __version__ as core_version
from lightrag.constants import (
    DEFAULT_FORCE_LLM_SUMMARY_ON_MERGE,
)
from fastapi import HTTPException, Security, Request, status
from fastapi.security import APIKeyHeader, OAuth2PasswordBearer
from starlette.status import HTTP_403_FORBIDDEN
from .auth import auth_handler
from .config import ollama_server_infos, global_args, get_env_value


def check_env_file():
    """
    检查.env文件是否存在，并在需要时处理用户确认。
    如果应继续则返回True，如果应退出则返回False。
    """
    if not os.path.exists(".env"):
        warning_msg = "警告：启动目录必须包含.env文件以支持多实例。"
        ASCIIColors.yellow(warning_msg)

        # 检查是否在交互式终端中运行
        if sys.stdin.isatty():
            response = input("是否继续？(yes/no): ")
            if response.lower() != "yes":
                ASCIIColors.red("服务器启动已取消")
                return False
    return True


# 从global_args获取白名单路径，初始化时仅执行一次
whitelist_paths = global_args.whitelist_paths.split(",")

# 预编译路径匹配模式
whitelist_patterns: List[Tuple[str, bool]] = []
for path in whitelist_paths:
    path = path.strip()
    if path:
        # 如果路径以/*结尾，则匹配具有该前缀的所有路径
        if path.endswith("/*"):
            prefix = path[:-2]
            whitelist_patterns.append((prefix, True))  # (前缀, 是否前缀匹配)
        else:
            whitelist_patterns.append((path, False))  # (精确路径, 是否前缀匹配)

# 全局认证配置
auth_configured = bool(auth_handler.accounts)


def get_combined_auth_dependency(api_key: Optional[str] = None):
    """
    创建一个组合认证依赖项，根据API密钥、OAuth2令牌和白名单路径实现认证逻辑。

    参数:
        api_key (Optional[str]): 用于验证的API密钥

    返回:
        Callable: 实现认证逻辑的依赖函数
    """
    # 使用全局whitelist_patterns和auth_configured变量
    # whitelist_patterns和auth_configured已在模块级别初始化

    # 仅计算api_key_configured，因为它取决于函数参数
    api_key_configured = bool(api_key)

    # 创建带有适当描述的安全依赖项，用于Swagger UI
    oauth2_scheme = OAuth2PasswordBearer(
        tokenUrl="login", auto_error=False, description="OAuth2密码认证"
    )

    # 如果配置了API密钥，则创建API密钥头安全
    api_key_header = None
    if api_key_configured:
        api_key_header = APIKeyHeader(
            name="X-API-Key", auto_error=False, description="API密钥认证"
        )

    async def combined_dependency(
        request: Request,
        token: str = Security(oauth2_scheme),
        api_key_header_value: Optional[str] = None
        if api_key_header is None
        else Security(api_key_header),
    ):
        # 1. 检查路径是否在白名单中
        path = request.url.path
        for pattern, is_prefix in whitelist_patterns:
            if (is_prefix and path.startswith(pattern)) or (
                not is_prefix and path == pattern
            ):
                return  # 白名单路径，允许访问

        # 2. 如果提供了令牌，则首先验证令牌（如果令牌无效则确保返回401错误）
        if token:
            try:
                token_info = auth_handler.validate_token(token)
                # 如果未配置认证且令牌为访客令牌，则接受
                if not auth_configured and token_info.get("role") == "guest":
                    return
                # 如果配置了认证且令牌不是访客令牌，则接受
                if auth_configured and token_info.get("role") != "guest":
                    return

                # 令牌验证失败，立即返回401错误
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="无效令牌。请重新登录。",
                )
            except HTTPException as e:
                # 如果已经是401错误，则重新抛出
                if e.status_code == status.HTTP_401_UNAUTHORIZED:
                    raise
                # 对于其他异常，继续处理

        # 3. 如果不需要API保护，则接受所有请求
        if not auth_configured and not api_key_configured:
            return

        # 4. 如果提供了API密钥且配置了API密钥认证，则验证API密钥
        if (
            api_key_configured
            and api_key_header_value
            and api_key_header_value == api_key
        ):
            return  # API密钥验证成功

        ### 认证失败 ####

        # 如果配置了密码认证但未提供令牌，且已配置认证，则确保返回401错误
        if auth_configured and not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="未提供凭据。请登录。",
            )

        # 如果提供了API密钥但验证失败
        if api_key_header_value:
            raise HTTPException(
                status_code=HTTP_403_FORBIDDEN,
                detail="无效的API密钥",
            )

        # 如果配置了API密钥但未提供
        if api_key_configured and not api_key_header_value:
            raise HTTPException(
                status_code=HTTP_403_FORBIDDEN,
                detail="需要API密钥",
            )

        # 否则：拒绝访问并返回403错误
        raise HTTPException(
            status_code=HTTP_403_FORBIDDEN,
            detail="需要API密钥或登录认证。",
        )

    return combined_dependency


def display_splash_screen(args: argparse.Namespace) -> None:
    """
    显示显示LightRAG服务器配置的彩色启动画面

    参数:
        args: 已解析的命令行参数
    """
    # 横幅
    top_border = "╔══════════════════════════════════════════════════════════════╗"
    bottom_border = "╚══════════════════════════════════════════════════════════════╝"
    width = len(top_border) - 4  # 边框内的宽度

    line1_text = f"LightRAG服务器 v{core_version}/{api_version}"
    line2_text = "快速、轻量级的RAG服务器实现"

    line1 = f"║ {line1_text.center(width)} ║"
    line2 = f"║ {line2_text.center(width)} ║"

    banner = f"""
    {top_border}
    {line1}
    {line2}
    {bottom_border}
    """
    ASCIIColors.cyan(banner)

    # 服务器配置
    ASCIIColors.magenta("\n📡 服务器配置:")
    ASCIIColors.white("    ├─ 主机: ", end="")
    ASCIIColors.yellow(f"{args.host}")
    ASCIIColors.white("    ├─ 端口: ", end="")
    ASCIIColors.yellow(f"{args.port}")
    ASCIIColors.white("    ├─ 工作进程数: ", end="")
    ASCIIColors.yellow(f"{args.workers}")
    ASCIIColors.white("    ├─ 超时时间: ", end="")
    ASCIIColors.yellow(f"{args.timeout}")
    ASCIIColors.white("    ├─ CORS来源: ", end="")
    ASCIIColors.yellow(f"{args.cors_origins}")
    ASCIIColors.white("    ├─ SSL启用: ", end="")
    ASCIIColors.yellow(f"{args.ssl}")
    if args.ssl:
        ASCIIColors.white("    ├─ SSL证书: ", end="")
        ASCIIColors.yellow(f"{args.ssl_certfile}")
        ASCIIColors.white("    ├─ SSL密钥: ", end="")
        ASCIIColors.yellow(f"{args.ssl_keyfile}")
    ASCIIColors.white("    ├─ Ollama模拟模型: ", end="")
    ASCIIColors.yellow(f"{ollama_server_infos.LIGHTRAG_MODEL}")
    ASCIIColors.white("    ├─ 日志级别: ", end="")
    ASCIIColors.yellow(f"{args.log_level}")
    ASCIIColors.white("    ├─ 详细调试: ", end="")
    ASCIIColors.yellow(f"{args.verbose}")
    ASCIIColors.white("    ├─ API密钥: ", end="")
    ASCIIColors.yellow("已设置" if args.key else "未设置")
    ASCIIColors.white("    └─ JWT认证: ", end="")
    ASCIIColors.yellow("已启用" if args.auth_accounts else "已禁用")

    # 目录配置
    ASCIIColors.magenta("\n📂 目录配置:")
    ASCIIColors.white("    ├─ 工作目录: ", end="")
    ASCIIColors.yellow(f"{args.working_dir}")
    ASCIIColors.white("    └─ 输入目录: ", end="")
    ASCIIColors.yellow(f"{args.input_dir}")

    # LLM配置
    ASCIIColors.magenta("\n🤖 LLM配置:")
    ASCIIColors.white("    ├─ 绑定: ", end="")
    ASCIIColors.yellow(f"{args.llm_binding}")
    ASCIIColors.white("    ├─ 主机: ", end="")
    ASCIIColors.yellow(f"{args.llm_binding_host}")
    ASCIIColors.white("    ├─ 模型: ", end="")
    ASCIIColors.yellow(f"{args.llm_model}")
    ASCIIColors.white("    ├─ LLM最大并发数: ", end="")
    ASCIIColors.yellow(f"{args.max_async}")
    ASCIIColors.white("    ├─ 摘要上下文大小: ", end="")
    ASCIIColors.yellow(f"{args.summary_context_size}")
    ASCIIColors.white("    ├─ LLM缓存启用: ", end="")
    ASCIIColors.yellow(f"{args.enable_llm_cache}")
    ASCIIColors.white("    └─ 提取启用LLM缓存: ", end="")
    ASCIIColors.yellow(f"{args.enable_llm_cache_for_extract}")

    # 嵌入配置
    ASCIIColors.magenta("\n📊 嵌入配置:")
    ASCIIColors.white("    ├─ 绑定: ", end="")
    ASCIIColors.yellow(f"{args.embedding_binding}")
    ASCIIColors.white("    ├─ 主机: ", end="")
    ASCIIColors.yellow(f"{args.embedding_binding_host}")
    ASCIIColors.white("    ├─ 模型: ", end="")
    ASCIIColors.yellow(f"{args.embedding_model}")
    ASCIIColors.white("    └─ 维度: ", end="")
    ASCIIColors.yellow(f"{args.embedding_dim}")

    # RAG配置
    ASCIIColors.magenta("\n⚙️ RAG配置:")
    ASCIIColors.white("    ├─ 摘要语言: ", end="")
    ASCIIColors.yellow(f"{args.summary_language}")
    ASCIIColors.white("    ├─ 实体类型: ", end="")
    ASCIIColors.yellow(f"{args.entity_types}")
    ASCIIColors.white("    ├─ 最大并行插入: ", end="")
    ASCIIColors.yellow(f"{args.max_parallel_insert}")
    ASCIIColors.white("    ├─ 块大小: ", end="")
    ASCIIColors.yellow(f"{args.chunk_size}")
    ASCIIColors.white("    ├─ 块重叠大小: ", end="")
    ASCIIColors.yellow(f"{args.chunk_overlap_size}")
    ASCIIColors.white("    ├─ 余弦阈值: ", end="")
    ASCIIColors.yellow(f"{args.cosine_threshold}")
    ASCIIColors.white("    ├─ Top-K: ", end="")
    ASCIIColors.yellow(f"{args.top_k}")
    ASCIIColors.white("    └─ 合并时强制LLM摘要: ", end="")
    ASCIIColors.yellow(
        f"{get_env_value('FORCE_LLM_SUMMARY_ON_MERGE', DEFAULT_FORCE_LLM_SUMMARY_ON_MERGE, int)}"
    )

    # 系统配置
    ASCIIColors.magenta("\n💾 存储配置:")
    ASCIIColors.white("    ├─ KV存储: ", end="")
    ASCIIColors.yellow(f"{args.kv_storage}")
    ASCIIColors.white("    ├─ 向量存储: ", end="")
    ASCIIColors.yellow(f"{args.vector_storage}")
    ASCIIColors.white("    ├─ 图存储: ", end="")
    ASCIIColors.yellow(f"{args.graph_storage}")
    ASCIIColors.white("    ├─ 文档状态存储: ", end="")
    ASCIIColors.yellow(f"{args.doc_status_storage}")
    ASCIIColors.white("    └─ 工作区: ", end="")
    ASCIIColors.yellow(f"{args.workspace if args.workspace else '-'}")

    # 服务器状态
    ASCIIColors.green("\n✨ 服务器正在启动...\n")

    # 服务器访问信息
    protocol = "https" if args.ssl else "http"
    if args.host == "0.0.0.0":
        ASCIIColors.magenta("\n🌐 服务器访问信息:")
        ASCIIColors.white("    ├─ WebUI (本地): ", end="")
        ASCIIColors.yellow(f"{protocol}://localhost:{args.port}")
        ASCIIColors.white("    ├─ 远程访问: ", end="")
        ASCIIColors.yellow(f"{protocol}://<你的IP地址>:{args.port}")
        ASCIIColors.white("    ├─ API文档 (本地): ", end="")
        ASCIIColors.yellow(f"{protocol}://localhost:{args.port}/docs")
        ASCIIColors.white("    └─ 替代文档 (本地): ", end="")
        ASCIIColors.yellow(f"{protocol}://localhost:{args.port}/redoc")

        ASCIIColors.magenta("\n📝 注意:")
        ASCIIColors.cyan("""    由于服务器运行在0.0.0.0上:
    - 使用'localhost'或'127.0.0.1'进行本地访问
    - 使用您的机器IP地址进行远程访问
    - 查找您的IP地址:
      • Windows: 在终端运行'ipconfig'
      • Linux/Mac: 在终端运行'ifconfig'或'ip addr'
    """)
    else:
        base_url = f"{protocol}://{args.host}:{args.port}"
        ASCIIColors.magenta("\n🌐 服务器访问信息:")
        ASCIIColors.white("    ├─ WebUI (本地): ", end="")
        ASCIIColors.yellow(f"{base_url}")
        ASCIIColors.white("    ├─ API文档: ", end="")
        ASCIIColors.yellow(f"{base_url}/docs")
        ASCIIColors.white("    └─ 替代文档: ", end="")
        ASCIIColors.yellow(f"{base_url}/redoc")

    # 安全通知
    if args.key:
        ASCIIColors.yellow("\n⚠️  安全通知:")
        ASCIIColors.white("""    API密钥认证已启用。
    请确保在所有请求中包含X-API-Key头。
    """)
    if args.auth_accounts:
        ASCIIColors.yellow("\n⚠️  安全通知:")
        ASCIIColors.white("""    JWT认证已启用。
    请确保在发出请求前登录，并在头中包含'Authorization'。
    """)

    # 确保启动画面输出刷新到系统日志
    sys.stdout.flush()