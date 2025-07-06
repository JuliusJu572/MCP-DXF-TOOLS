"""
remote-dxf-server.py
集成版 DXF 处理服务器：FastAPI + MCP
支持文件上传、下载和 MCP 工具调用

部署方式：
1. 本地测试：python remote-dxf-server.py
2. 阿里云部署：使用 uvicorn 或 gunicorn

Cline 配置：
{
  "mcpServers": {
    "dxf-processor": {
      "url": "http://your-server.com/mcp-server/sse",
      "transport": "sse"
    }
  }
}

使用流程：
1. 上传文件：POST /upload
例如：curl.exe -X POST -F "file=@管线-燃气.dxf" http://101.132.89.101:8000/upload
2. 调用 MCP 工具处理
3. 下载结果：GET /download/{file_id}
例如：curl.exe http://101.132.89.101:8000/download/ad2cf1fe-574e-471a-95f0-4da5a20b0783 --output 管线-燃气_result.csv
"""

from pathlib import Path
import csv
import ezdxf
from ezdxf.layouts import Modelspace
from tqdm import tqdm
import uuid
import tempfile
import os
import shutil
from typing import Dict, Optional

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from fastmcp import FastMCP
import socket
import requests
import os

# ----------------------------------------------------------------------
# 创建 FastAPI 应用和 MCP 服务器
# ----------------------------------------------------------------------
mcp = FastMCP("CAD-DXF 工具服务", dependencies=["ezdxf", "tqdm", "fastapi", "uvicorn", "requests"])
mcp_app = mcp.sse_app()
app = FastAPI(lifespan=mcp_app.router.lifespan_context)
# 添加 CORS 支持
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ----------------------------------------------------------------------
# 文件存储管理
# ----------------------------------------------------------------------
class FileManager:
    def __init__(self, upload_dir: str = "./uploads", result_dir: str = "./results"):
        self.upload_dir = Path(upload_dir)
        self.result_dir = Path(result_dir)
        self.upload_dir.mkdir(exist_ok=True)
        self.result_dir.mkdir(exist_ok=True)

        # 存储文件信息
        self.files: Dict[str, Dict] = {}

    def save_upload(self, file: UploadFile) -> str:
        """保存上传的文件，返回文件 ID"""
        file_id = str(uuid.uuid4())
        file_path = self.upload_dir / f"{file_id}_{file.filename}"

        # 保存文件
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # 记录文件信息
        self.files[file_id] = {
            "original_name": file.filename,
            "file_path": str(file_path),
            "file_size": file_path.stat().st_size,
            "content_type": file.content_type,
            "status": "uploaded"
        }

        return file_id

    def get_file_path(self, file_id: str) -> Optional[str]:
        """获取文件路径"""
        if file_id in self.files:
            return self.files[file_id]["file_path"]
        return None

    def get_file_info(self, file_id: str) -> Optional[Dict]:
        """获取文件信息"""
        return self.files.get(file_id)

    def save_result(self, file_id: str, result_content: str, result_type: str = "csv") -> str:
        """保存处理结果，返回结果文件路径"""
        if file_id not in self.files:
            raise ValueError(f"文件 ID {file_id} 不存在")

        original_name = self.files[file_id]["original_name"]
        result_filename = f"{Path(original_name).stem}_result.{result_type}"
        result_path = self.result_dir / f"{file_id}_{result_filename}"

        with open(result_path, "w", encoding="utf-8-sig") as f:
            f.write(result_content)

        # 更新文件信息
        self.files[file_id]["result_path"] = str(result_path)
        self.files[file_id]["result_filename"] = result_filename
        self.files[file_id]["status"] = "processed"

        return str(result_path)


# 全局文件管理器
file_manager = FileManager()


# ----------------------------------------------------------------------
# FastAPI 端点
# ----------------------------------------------------------------------

@app.get("/")
async def root():
    """服务状态检查"""
    return {
        "service": "DXF 处理服务",
        "status": "运行中",
        "endpoints": {
            "upload": "POST /upload - 上传 DXF 文件",
            "download": "GET /download/{file_id} - 下载处理结果",
            "files": "GET /files/{file_id} - 获取文件信息",
            "mcp-server": "/mcp-server/* - MCP 工具端点"
        }
    }


@app.post("/upload")
async def upload_dxf_file(file: UploadFile = File(...)):
    """
    上传 DXF 文件

    返回：
    - file_id: 文件唯一标识符
    - filename: 原始文件名
    - size: 文件大小
    """
    try:
        # 检查文件类型
        if not file.filename.lower().endswith('.dxf'):
            raise HTTPException(status_code=400, detail="只支持 DXF 文件格式")

        # 保存文件
        file_id = file_manager.save_upload(file)
        file_info = file_manager.get_file_info(file_id)

        return {
            "file_id": file_id,
            "filename": file_info["original_name"],
            "size": file_info["file_size"],
            "message": "DXF 文件上传成功",
            "next_step": "使用 MCP 工具 'inspect_uploaded_dxf' 或 'process_uploaded_dxf' 处理文件"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文件上传失败: {str(e)}")


@app.get("/files/{file_id}")
async def get_file_info(file_id: str):
    """获取文件信息"""
    file_info = file_manager.get_file_info(file_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="文件不存在")

    return file_info


@app.get("/download/{file_id}")
async def download_result_file(file_id: str):
    """下载处理结果文件"""
    file_info = file_manager.get_file_info(file_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="文件不存在")

    if "result_path" not in file_info:
        raise HTTPException(status_code=400, detail="文件尚未处理或处理失败")

    result_path = file_info["result_path"]
    if not Path(result_path).exists():
        raise HTTPException(status_code=404, detail="结果文件不存在")

    return FileResponse(
        result_path,
        filename=file_info["result_filename"],
        media_type="text/csv"
    )


# ----------------------------------------------------------------------
# MCP 工具（修改后的版本）
# ----------------------------------------------------------------------

@mcp.tool(name="检查已上传 DXF 文件的结构并列出 XDATA")
def inspect_uploaded_dxf(
        file_id: str,
        max_entities: int | None = 200,
) -> list[str]:
    """
    分析已上传 DXF 文件中实体的类型、图层信息与 XDATA 数据。

    重要：如果您是第一次使用此服务，请先调用 'get_service_info' 工具了解如何上传文件。

    使用前提条件：
    1. 必须先上传 DXF 文件获取 file_id
    2. 如果没有 file_id，请先调用 'get_service_info' 获取上传方法
    3. 上传命令示例：curl.exe -X POST -F "file=@用户提供的本地文件路径.dxf" http://101.132.89.101:8000/upload

    参数：
    - file_id (str): 上传文件后获得的唯一标识符
    - max_entities (int | None): 最大显示实体数量，默认为 200

    返回：
    - list[str]: 每个实体的摘要信息（类型、图层、XDATA）
    """
    messages: list[str] = []

    # 获取文件路径
    filepath = file_manager.get_file_path(file_id)
    if not filepath:
        return [f"错误：文件 ID {file_id} 不存在"]

    try:
        doc = ezdxf.readfile(filepath)
        msp: Modelspace = doc.modelspace()
    except (IOError, ezdxf.DXFStructureError) as e:
        return [f"加载 DXF 文件失败: {e}"]

    file_info = file_manager.get_file_info(file_id)
    messages.append(
        f"文件 {file_info['original_name']} 加载成功 (ezdxf v{ezdxf.__version__})，模型空间共有 {len(msp)} 个实体。"
    )

    for idx, ent in enumerate(msp):
        if max_entities and idx >= max_entities:
            messages.append("...(已截断其余实体输出)")
            break

        line = f"[{idx + 1}] 类型:{ent.dxftype()} 图层:{ent.dxf.layer}"
        if ent.has_xdata and ent.xdata is not None:
            x_parts = []
            for app in ent.xdata.data:
                codes = [f"{c}:{v}" for c, v in ent.xdata.get(app)]
                x_parts.append(f"{app}({', '.join(codes)})")
            line += " | XDATA: " + "; ".join(x_parts)
        messages.append(line)
    return messages


@mcp.tool(name="处理已上传 DXF 文件并生成 CSV")
def process_uploaded_dxf(
        file_id: str,
) -> dict:
    """
    处理已上传的 DXF 文件并生成 CSV（位置、图层、文本、XDATA 等）。

    重要：如果您是第一次使用此服务，请先调用 'get_service_info' 工具获取完整的使用说明和工作流程。

    使用前提条件：
    1. 必须先上传 DXF 文件获取 file_id，file_id不是用户给的本地文件的文件名，是在上传服务器后才能得到的。
    2. 上传命令示例：curl.exe -X POST -F "file=@your_file.dxf" http://服务器地址/upload

    如果您没有 file_id，请：
    - 调用 'get_service_info' 获取上传方法
    - 上传文件后再使用此工具

    参数：
    - file_id (str): 上传文件后获得的唯一标识符

    返回：
    - dict: 处理结果，包含状态、文件信息和下载链接
    """
    # 获取文件路径
    filepath = file_manager.get_file_path(file_id)
    if not filepath:
        return {"error": f"文件 ID {file_id} 不存在"}

    file_info = file_manager.get_file_info(file_id)

    try:
        # 读取 DXF
        doc = ezdxf.readfile(filepath)
        msp = doc.modelspace()

        # 转换为 CSV
        rows: list[dict] = []
        for ent in tqdm(msp, desc="解析实体"):
            row = {
                "Handle": ent.dxf.handle,
                "EntityType": ent.dxftype(),
                "Layer": ent.dxf.layer,
                "Position": "N/A",
            }

            etype = ent.dxftype()
            if etype in ("POLYLINE", "LWPOLYLINE"):
                pts = [f"({p.x:.3f},{p.y:.3f},{p.z:.3f})" for p in ent.points()]
                row["Position"] = "; ".join(pts)
            elif etype == "LINE":
                s, e = ent.dxf.start, ent.dxf.end
                row["Position"] = (
                    f"Start({s.x:.3f},{s.y:.3f},{s.z:.3f});"
                    f"End({e.x:.3f},{e.y:.3f},{e.z:.3f})"
                )
            elif etype == "INSERT":
                p = ent.dxf.insert
                row["Position"] = f"({p.x:.3f},{p.y:.3f},{p.z:.3f})"
                row["BlockName"] = ent.dxf.name
            elif etype in ("TEXT", "MTEXT"):
                p = ent.dxf.insert
                row["Position"] = f"({p.x:.3f},{p.y:.3f},{p.z:.3f})"
                row["TextValue"] = ent.dxf.text if etype == "TEXT" else ent.plain_text()
            elif etype in ("CIRCLE", "ARC"):
                c = ent.dxf.center
                row["Position"] = f"Center({c.x:.3f},{c.y:.3f},{c.z:.3f})"
                row["Radius"] = ent.dxf.radius
            elif etype == "SPLINE":
                pts = [f"({p.x:.3f},{p.y:.3f},{p.z:.3f})" for p in ent.control_points]
                row["Position"] = "; ".join(pts)

            if ent.has_xdata and ent.xdata is not None:
                for app in ent.xdata.data:
                    for code, value in ent.xdata.get(app):
                        if code == 1000:
                            row[app] = value
                            break

            rows.append(row)

        if not rows:
            return {"warning": f"DXF 文件中未发现任何实体"}

        # 生成 CSV 内容
        fieldnames = set().union(*(r.keys() for r in rows))
        preferred = [
            "Handle",
            "EntityType",
            "Layer",
            "BlockName",
            "TextValue",
            "Radius",
            "Position",
        ]
        final_fields = preferred + sorted(f for f in fieldnames if f not in preferred)

        # 写入 CSV 字符串
        import io
        csv_buffer = io.StringIO()
        writer = csv.DictWriter(csv_buffer, final_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        csv_content = csv_buffer.getvalue()

        # 保存结果文件
        result_path = file_manager.save_result(file_id, csv_content, "csv")

        return {
            "status": "converted",
            "file_id": file_id,
            "filename": file_info["original_name"],
            "entity_count": len(rows),
            "csv_rows": len(rows),
            "download_url": f"/download/{file_id}",
            "message": f"转换完成：{len(rows)} 个实体已导出为 CSV",
            "result_filename": file_info["result_filename"]
        }


    except Exception as e:
        return {"error": f"DXF 处理失败: {str(e)}"}


@mcp.tool(name="获取服务信息")
def get_service_info() -> dict:
    """
    获取 DXF 处理服务的完整使用说明、服务器地址和工作流程。

    此工具会返回：
    - 服务器地址和连接信息
    - 完整的文件上传步骤
    - 所有可用的 MCP 工具说明
    - 详细的使用示例

    重要：首次使用服务时请先调用此工具了解完整流程。
    """

    # 获取公网 IP 地址
    def get_public_ip():
        try:
            # 尝试多个服务获取公网 IP
            services = [
                "https://api.ipify.org",
                "https://ifconfig.me/ip",
                "https://icanhazip.com"
            ]
            for service in services:
                try:
                    response = requests.get(service, timeout=5)
                    if response.status_code == 200:
                        return response.text.strip()
                except:
                    continue
            return "未知"
        except:
            return "未知"

    # 检测运行端口
    def get_server_port():
        # 从环境变量或默认值获取端口
        port = os.environ.get('PORT', '8000')
        return port

    public_ip = get_public_ip()
    port = get_server_port()

    public_address = f"http://{public_ip}:{port}" if public_ip != "未知" else "未知"

    return {
        "service": "DXF 处理服务",
        "version": "1.0.0",
        "server_info": {
            "public_ip": public_ip,
            "port": port,
            "public_address": public_address,
            "status": "运行中"
        },
        "endpoints": {
            "服务状态": f"GET {public_address}/ - 服务状态检查",
            "上传文件": f"POST {public_address}/upload - 上传 DXF 文件",
            "下载结果": f"GET {public_address}/download/{{file_id}} - 下载处理结果",
            "文件信息": f"GET {public_address}/files/{{file_id}} - 获取文件信息",
            "MCP服务": f"{public_address}/mcp-server/sse - MCP 工具端点"
        },
        "access_urls": {
            "公网访问": public_address,
            "MCP连接": f"{public_address}/mcp-server/sse"
        },
        "workflow": [
            f"1. 上传 DXF 文件: curl.exe -X POST -F 'file=@your_file.dxf' {public_address}/upload",
            "2. 获取返回的 file_id",
            "3. 使用 MCP 工具处理文件",

            f"4. 下载结果: curl.exe {public_address}/download/{{file_id}} --output xxx"
        ],
        "mcp_tools": [
            "inspect_uploaded_dxf - 分析 DXF 结构",
            "process_uploaded_dxf - 转换为 CSV",
            "get_service_info - 获取服务信息"
        ],
        "cline_config": {
            "mcpServers": {
                "dxf-processor": {
                    "url": f"{public_address}/mcp-server/sse",
                    "transport": "sse"
                }
            }
        },
    }

# ----------------------------------------------------------------------
# 集成 MCP 服务到 FastAPI
# ----------------------------------------------------------------------

# 将 MCP 服务挂载到 /mcp-server 路径
app.mount("/mcp-server", mcp_app)

# ----------------------------------------------------------------------
# 服务启动
# ----------------------------------------------------------------------

if __name__ == "__main__":
    print("启动Remote版 DXF 处理服务...")
    print("上传端点: POST /upload")
    print("MCP 端点: /mcp-server/sse")
    print("下载端点: GET /download/{file_id}")
    print("服务信息: GET /")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=False  # 开发模式，生产环境设为 False
    )