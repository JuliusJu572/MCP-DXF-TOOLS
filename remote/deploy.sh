#!/bin/bash
# deploy.sh - 一键部署脚本

set -e  # 遇到错误立即退出

echo "🚀 开始部署 DXF 处理服务..."

# 检查 Docker 是否安装
if ! command -v docker &> /dev/null; then
    echo "❌ Docker 未安装，请先安装 Docker"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose 未安装，请先安装 Docker Compose"
    exit 1
fi

# 创建必要的目录
echo "📁 创建数据目录..."
mkdir -p data/uploads data/results logs

# 设置权限
chmod 755 data/uploads data/results

# 构建镜像
echo "🔨 构建 Docker 镜像..."
docker-compose build

# 启动服务
echo "🚀 启动服务..."
docker-compose up -d

# 等待服务启动
echo "⏳ 等待服务启动..."
sleep 10

# 健康检查
echo "🏥 检查服务健康状态..."
for i in {1..30}; do
    if curl -f http://localhost:8000/ &> /dev/null; then
        echo "✅ 服务启动成功！"
        break
    fi

    if [ $i -eq 30 ]; then
        echo "❌ 服务启动失败，请检查日志"
        docker-compose logs
        exit 1
    fi

    echo "等待中... ($i/30)"
    sleep 2
done

# 显示服务信息
echo ""
echo "🎉 部署完成！"
echo "📋 服务信息："
echo "   - 服务地址: http://localhost:8000"
echo "   - 上传接口: POST http://localhost:8000/upload"
echo "   - MCP 端点: http://localhost:8000/mcp/sse"
echo "   - 服务状态: http://localhost:8000/"
echo ""
echo "📊 查看日志: docker-compose logs -f"
echo "🛑 停止服务: docker-compose down"
echo "🔄 重启服务: docker-compose restart"

# Cline 配置信息
echo ""
echo "🔧 Cline 配置："
echo '{
  "mcpServers": {
    "dxf-processor": {
      "url": "http://localhost:8000/mcp/sse",
      "transport": "sse"
    }
  }
}'