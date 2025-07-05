"""
dxf_server.py
暴露两个 MCP 工具：
1. inspect_dxf_structure  —— 预览 DXF 结构与 XDATA
2. dxf_entities_to_csv    —— 提取实体+XDATA 并导出为 CSV
"""

from pathlib import Path
import csv
import ezdxf
from ezdxf.layouts import Modelspace
from tqdm import tqdm

from mcp.server.fastmcp import FastMCP  # FastMCP：最简单的 MCP 服务器实现

# ----------------------------------------------------------------------
# 创建 MCP 服务器实例（指定依赖方便在 Claude Desktop / mcp.dev 一键部署）
# ----------------------------------------------------------------------
mcp = FastMCP("CAD-DXF 工具服务", dependencies=["ezdxf", "tqdm"])

# ----------------------------------------------------------------------
#  工具 1：检查 DXF 结构 & XDATA
# ----------------------------------------------------------------------
@mcp.tool(title="检查 DXF 结构并列出 XDATA")
def inspect_dxf_structure(
    filepath: str,
    max_entities: int | None = 200,
) -> list[str]:
    """
    分析并预览 DXF 文件中前若干个实体的类型、图层信息与 XDATA 数据。

    参数：
    - filepath (str): DXF 文件的路径。
    - max_entities (int | None): 最大显示实体数量，默认为 200。若为 None，则输出全部实体。

    返回：
    - list[str]: 每个实体的摘要信息（包含类型、图层及 XDATA 简述）。
    """
    messages: list[str] = []
    try:
        doc = ezdxf.readfile(filepath)
        msp: Modelspace = doc.modelspace()
    except (IOError, ezdxf.DXFStructureError) as e:
        return [f"加载 DXF 文件失败: {e}"]

    messages.append(
        f"文件加载成功 (ezdxf v{ezdxf.__version__})，模型空间共有 {len(msp)} 个实体。"
    )

    for idx, ent in enumerate(msp):
        if max_entities and idx >= max_entities:
            messages.append("...(已截断其余实体输出)")
            break

        line = f"[{idx+1}] 类型:{ent.dxftype()} 图层:{ent.dxf.layer}"
        if ent.has_xdata and ent.xdata is not None:
            x_parts = []
            for app in ent.xdata.data:
                codes = [f"{c}:{v}" for c, v in ent.xdata.get(app)]
                x_parts.append(f"{app}({', '.join(codes)})")
            line += " | XDATA: " + "; ".join(x_parts)
        messages.append(line)
    return messages


# ----------------------------------------------------------------------
#  工具 2：DXF → CSV
# ----------------------------------------------------------------------
@mcp.tool(title="提取 DXF 实体并导出 CSV")
def dxf_entities_to_csv(
    filepath: str,
    output_csv: str | None = None,
) -> str:
    """
    将 DXF 文件中的所有实体及其属性（位置、图层、文本、XDATA 等）提取并保存为 CSV 表格。

    参数：
    - filepath (str): 输入的 DXF 文件路径。
    - output_csv (str | None): 可选，输出 CSV 文件路径。若未指定，将默认保存为与 DXF 同名的 CSV 文件。

    返回：
    - str: 实际生成的 CSV 文件路径。
    """
    try:
        # 路径处理
        filepath = Path(filepath)
        if not filepath.exists():
            return f"[错误] 输入文件不存在：{filepath}"

        if output_csv is None:
            output_csv = filepath.with_suffix(".csv")
        else:
            output_csv = Path(output_csv)

        # 读取 DXF
        doc = ezdxf.readfile(str(filepath))
        msp = doc.modelspace()

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
            return f"[警告] DXF 中未发现任何实体：{filepath}"

        # 写 CSV
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

        output_csv.parent.mkdir(parents=True, exist_ok=True)  # 确保目录存在
        with open(output_csv, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, final_fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)

        return f"[成功] CSV 文件已生成：{output_csv.resolve()}"

    except Exception as e:
        return f"[错误] DXF 解析或导出失败：{e}"


if __name__ == "__main__":
    mcp.run(transport="stdio")