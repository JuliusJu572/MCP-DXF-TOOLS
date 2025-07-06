# Dockerfile
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app


# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --no-cache-dir -r requirements.txt

# 复制应用代码
COPY remote-dxf-server.py .
COPY gunicorn.conf.py .

# 创建必要的目录
RUN mkdir -p /app/uploads /app/results

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# 暴露端口
EXPOSE 8000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/ || exit 1

# 使用 Gunicorn 启动应用
CMD ["gunicorn", "remote-dxf-server:app", "-c", "gunicorn.conf.py"]