## 🔧 工具环境

- 使用开发工具：`Cursor` + `cline`
- 使用包管理器：`uv`
- 核心依赖：`ezdxf`, `tqdm`, `mcp[cli]`

## 🚀 创建工程

```bash
uv init my-mcp-server
cd my-mcp-server
uv add ezdxf "mcp[cli]"
```

## 🧠 MCP 主程序封装

创建文件 `dxf_server.py`，实现两个 MCP 工具：

``` python
"""
dxf_server.py
暴露两个 MCP 工具：
1. inspect_dxf_structure  —— 预览 DXF 结构与 XDATA
2. dxf_entities_to_csv    —— 提取实体+XDATA 并导出为 CSV
"""

  

from pathlib import Path
import csv
import ezdxf
from ezdxf.layouts import Modelspace
from tqdm import tqdm
from mcp.server.fastmcp import FastMCP

# 创建 MCP 实例
mcp = FastMCP("CAD-DXF 工具服务", dependencies=["ezdxf", "tqdm"])

# 工具 1：检查 DXF 结构
@mcp.tool(title="检查 DXF 结构并列出 XDATA")
def inspect_dxf_structure(filepath: str, max_entities: int | None = 200) -> list[str]:
    ...
    # 实现见上文，提取类型、图层、XDATA

# 工具 2：DXF → CSV
@mcp.tool(title="提取 DXF 实体并导出 CSV")
def dxf_entities_to_csv(filepath: str, output_csv: str | None = None) -> str:
    ...
    # 实现见上文，提取实体属性、坐标、文本、XDATA，并写入 CSV

if __name__ == "__main__":
    mcp.run(transport="stdio")

```

##  📁 工程目录结构

```perl
my-mcp-server/
├── dxf_server.py        # MCP 主服务入口
├── pyproject.toml       # uv 项目配置
└── cad-mcp-server/
    └── dxf/
        ├── 管线-燃气.dxf
        └── 管线-燃气.csv
```

## ⚙️ MCP Server 配置（`mcp.config.json`）

选择合适的model

![](imgs/select_models.png)

打开 mcp server

![](imgs/mcp_servers.png)

![](imgs/config_mcp_servers.png)



```json
{
  "mcpServers": {
    "dxf": {
      "disabled": false,
      "timeout": 60,
      "type": "stdio",
      "command": "uv",
      "args": [
        "--directory",
        "D:\\14_MCP\\my-mcp-server",
        "run",
        "dxf-server.py"
      ]
    }
  }
}
```

创建成功后

![](imgs/mcp_servers_installed.png)

## ✅ MCP 工具测试流程

💬 指令输入（Cline Prompt）

``` prompt
请调用工具“提取 DXF 实体并导出 CSV”，处理文件路径为：
./cad-mcp-server/dxf/管线-燃气.dxf，
并将输出 CSV 文件保存为：
./cad-mcp-server/dxf/管线-燃气.csv。
```

输出：

The tool execution failed again with the same error message indicating that the input file does not exist at 'cad-mcp-server\dxf\管线-燃气.dxf'. Despite trying backslashes, the issue persists. I need to consider if the path is incorrect or if there's another way to specify it.

Looking at the environment details, the file is listed under 'cad-mcp-server/dxf/管线-燃气.dxf' in the current working directory 'd:/14_MCP'. I should try using the full absolute path to ensure there is no ambiguity with relative paths. The full path would be 'd:/14_MCP/cad-mcp-server/dxf/管线-燃气.dxf'. I will also use forward slashes as they are generally accepted in Windows for programmatic paths and might resolve any parsing issues.

I will attempt the tool execution again with the absolute path to see if that resolves the issue.

Cline wants to use a tool on the `dxf` MCP server:

dxf_entities_to_csv

将 DXF 文件中的所有实体及其属性（位置、图层、文本、XDATA 等）提取并保存为 CSV 表格。 参数： - filepath (str): 输入的 DXF 文件路径。 - output_csv (str | None): 可选，输出 CSV 文件路径。若未指定，将默认保存为与 DXF 同名的 CSV 文件。 返回： - str: 实际生成的 CSV 文件路径，或错误信息。

Arguments

```json
{
  "filepath": "d:/14_MCP/cad-mcp-server/dxf/管线-燃气.dxf",
  "output_csv": "d:/14_MCP/cad-mcp-server/dxf/管线-燃气.csv"
}
```

Response

Rich Display

[成功] CSV 文件已生成：D:\14_MCP\cad-mcp-server\dxf\管线-燃气.csv

**Checkpoint

Compare

Restore

API Request$0.0000

I have confirmed from the user's response that the tool execution was successful, and the CSV file has been generated at 'D:\14_MCP\cad-mcp-server\dxf\管线-燃气.csv'. Since the task of extracting DXF entities and exporting them to a CSV file is complete, I can now present the result to the user using the attempt_completion tool.

Task Completed

I've successfully extracted the entities from the DXF file '管线-燃气.dxf' and exported them to the CSV file located at 'D:\14_MCP\cad-mcp-server\dxf\管线-燃气.csv'. The task is complete, and the CSV file contains all the entity attributes as requested.

## 🔁 总结流程图

```
1. uv init my-mcp-server ➜ 创建工程
2. uv add ezdxf mcp[cli] ➜ 安装依赖
3. 编写 dxf_server.py ➜ 封装 FastMCP 工具
4. 配置 mcp.config.json ➜ 挂载本地工具服务
5. cline prompt ➜ 指令调用 MCP 工具
6. dxf_entities_to_csv ➜ 提取实体写入 CSV
7. 检查输出路径并提示用户成功
```