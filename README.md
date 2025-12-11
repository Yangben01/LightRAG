用户请求 (LIGHTRAG-WORKSPACE: my_workspace)
↓
upload_to_input_dir 接收请求并提取 workspace
↓
background_tasks.add_task(pipeline_index_file, rag, file_path, track_id, category_id, workspace)
↓
[后台任务开始执行]
↓
pipeline_index_file:

1. 检查 workspace != rag.workspace
2. 初始化 pipeline_status(workspace) ← 关键！
3. 临时修改 rag 和所有存储实例的 workspace
4. 调用 pipeline_enqueue_file (入队文档到正确的 workspace)
5. 调用 apipeline_process_enqueue_documents (处理文档)
6. finally: 恢复原始 workspace

# 1. pipeline_index_file - 在整个任务执行期间维护正确的 workspace

async def pipeline_index_file(..., workspace: str = None):
original_workspace = None
if workspace and workspace != rag.workspace: # 🔑 关键：初始化 pipeline_status
await initialize_pipeline_status(workspace=workspace)

        # 修改所有存储实例的 workspace
        original_workspace = rag.workspace
        rag.workspace = workspace
        for storage in [rag.doc_status, rag.full_docs, ...]:
            storage.workspace = workspace

    try:
        # 处理文档
        success, _ = await pipeline_enqueue_file(rag, file_path, ...)
        if success:
            await rag.apipeline_process_enqueue_documents()
    finally:
        # 恢复 workspace
        if original_workspace:
            rag.workspace = original_workspace
            ...
