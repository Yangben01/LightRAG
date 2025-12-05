docker-compose build --no-cache
如需启动容器，运行：

docker-compose up -d

-- 启用 pgvector 扩展（仅需执行一次 per 数据库）
CREATE EXTENSION IF NOT EXISTS vector;

-- 验证扩展是否安装成功
SELECT * FROM pg_extension WHERE extname = 'vector';


-- 创建表，vector(3) 表示 3 维向量（维度可自定义，如 128、768 等）
CREATE TABLE IF NOT EXISTS embeddings (
    id SERIAL PRIMARY KEY,
    content TEXT,
    embedding vector(3)  -- 向量列，维度根据你的场景调整（如 AI 嵌入常用 768/1024）
);

-- 插入向量数据
INSERT INTO embeddings (content, embedding)
VALUES 
('苹果', '[1.2, 3.4, 5.6]'),
('香蕉', '[2.3, 4.5, 6.7]');

-- 查询向量（支持距离计算，如 L2 距离）
SELECT content, embedding <-> '[1.5, 3.5, 5.5]' AS l2_distance
FROM embeddings
ORDER BY l2_distance;