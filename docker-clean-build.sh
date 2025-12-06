#!/bin/bash
# Docker 清理并重建脚本

set -e  # 遇到错误时退出

echo "=========================================="
echo "Docker 深度清理并重建脚本"
echo "=========================================="

echo ""
echo "1. 正在停止并删除容器..."
docker-compose down -v 2>/dev/null || echo "   (没有运行的容器)"

echo ""
echo "2. 正在删除 LightRAG 相关镜像..."
docker rmi ghcr.io/hkuds/lightrag:latest 2>/dev/null || echo "   (镜像不存在或已被删除)"
docker images | grep lightrag | awk '{print $3}' | xargs -r docker rmi 2>/dev/null || echo "   (没有找到其他 LightRAG 镜像)"

echo ""
echo "3. 正在清理所有未使用的镜像..."
docker image prune -af

echo ""
echo "4. 正在清理构建缓存..."
docker builder prune -af

echo ""
echo "5. 正在清理未使用的卷..."
docker volume prune -f

echo ""
echo "6. 正在清理未使用的网络..."
docker network prune -f

echo ""
echo "7. 显示当前磁盘使用情况..."
docker system df

echo ""
echo "=========================================="
echo "开始重新构建镜像（无缓存）..."
echo "=========================================="
docker-compose build --no-cache

echo ""
echo "=========================================="
echo "完成！"
echo "=========================================="

