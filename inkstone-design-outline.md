# Inkstone 设计大纲

> 砚——把粗糙的墨条研磨成可以直接书写的墨汁。
> Inkstone 把非结构化文档转化为 AI Agent 可直接消费的结构化 Markdown。

---

## 1. 项目定位

Inkstone 是一个文档结构化提取工具，面向 AI Agent 生态设计。它解决的核心问题是：Agent 需要读取信源，但原始文档（PDF、DOCX、HTML）充满噪音，直接送入上下文会浪费 token 并干扰理解。

Inkstone 在代码层完成所有清洗和提取，Agent 只需调用一个接口，拿到干净的 Markdown + 资源文件。Agent 永远不碰原始文件内容。

**设计原则：**

- Agent 不碰原始文件内容：所有清洗、提取都在代码层完成
- 统一输出：无论输入什么格式，输出永远是 Markdown + 资源文件
- 信息零丢失：宁可多保留噪音，不可误删内容（`favor_recall`）
- 下游 Agent 是多模态模型：Inkstone 不做图片理解，只负责完整提取图片
- 跨 Agent 可用：同时提供 MCP Server 和 SKILL 两种接入方式


## 2. 架构总览

```
┌─────────────────────────────────────────────────┐
│                  Core Library                    │
│              pip install {org}-inkstone           │
│                                                  │
│  extract(path, format) → output_dir              │
│                                                  │
│  ┌───────────┐ ┌───────────┐ ┌────────────────┐ │
│  │  pdf.py   │ │  docx.py  │ │   html.py      │ │
│  │  Docling   │ │ python-   │ │  Trafilatura   │ │
│  │  +Paddle  │ │ docx      │ │  +BS4 预处理    │ │
│  │  OCR API  │ │           │ │                │ │
│  └───────────┘ └───────────┘ └────────────────┘ │
│        ▲                                         │
│  ┌─────┴──────┐                                  │
│  │ detect.py  │  扫描版 vs 文字版 自动判断        │
│  └────────────┘                                  │
└──────────────────┬──────────────────────────────┘
                   │
        ┌──────────┼──────────────┐
        ▼                         ▼
  MCP Server                    SKILL
  (mcp_server.py)               (SKILL.md + scripts/)
  跨 Agent 通用                  Claude Code 优化体验
```


## 3. 核心处理逻辑

### 3.1 统一入口

```python
def extract(path: str, format: str) -> str:
    """
    输入文件路径和格式，执行结构化提取。
    返回输出目录的路径。

    Args:
        path: 输入文件的路径
        format: 文件格式，"html" | "pdf" | "docx"

    Returns:
        输出目录路径（如 "/path/to/report/"）
    """
```

设计决策：
- **路由靠调用方传参 `format`**，不做自动检测，不做兜底校验。传错了直接报错，Agent 看到错误会自己修正
- **返回路径而非内容**：Agent 按需读取，不会被长文档撑爆上下文
- **输出目录在输入文件同级目录**：输入 `report.html` → 输出 `report/` 文件夹

### 3.2 PDF 路线

```
PDF 输入
  │
  └─ pdf.py extract_pdf(path)
       │
       ├─ detect.py is_scanned_pdf(path)  ← PyMuPDF 检测
       │
       ├─ 有文字层（文字版 PDF）
       │    → Docling（do_ocr=False, do_table_structure=True,
       │              generate_picture_images=True）
       │    → 输出 Markdown + 图片（Docling 原生格式）
       │
       └─ 无文字层（扫描版 PDF）
            → PaddleOCR 云端 API（PaddleOCR-VL-1.6）
            → 多页合并为一个 Markdown，<!-- Page N --> 标注页码
            → 输出 Markdown + 图片（PaddleOCR 原生格式）
```

**PDF 内部路由对 core.py 透明。** core.py 只调 `pdf.extract_pdf(path)`，不知道 Docling/PaddleOCR 的存在。扫描版/文字版判断、子路由都在 pdf.py 内部完成。

**文字版 — Docling 配置：**

```python
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions

opts = PdfPipelineOptions(
    do_ocr=False,
    do_table_structure=True,
    generate_picture_images=True,
)

converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=opts)
    }
)
```

技术选型理由：
- Docling（IBM，Apache 2.0）：内置 TableFormer 模型，金融表格处理最强；原生文字提取零幻觉；商用无风险
- 关闭 OCR 后 Docling 在 x86 CPU 上约 1-2 秒/页，笔记本可用
- 图片使用 Docling 原生命名和路径，不做后处理重命名

**扫描版 — PaddleOCR 云端 API：**

走百度 PaddleOCR 在线服务（`paddleocr.aistudio-app.com`），不安装本地 PaddlePaddle，只需要 `requests`。

```python
JOB_URL = "https://paddleocr.aistudio-app.com/api/v2/ocr/jobs"
MODEL = "PaddleOCR-VL-1.6"

optional_payload = {
    "useDocOrientationClassify": False,
    "useDocUnwarping": False,
    "useChartRecognition": False,
}
```

配置说明：
- `useChartRecognition=False`：图表只作为图片提取，不做结构化识别。符合"不做图片理解，下游 Agent 自己看图"原则
- `useDocOrientationClassify=False`：输入是 PDF 不是拍照，无需方向检测
- `useDocUnwarping=False`：PDF 无畸变，无需矫正

API 调用流程：
1. 提交任务（POST，上传文件或传 URL）
2. 同步阻塞轮询（GET，`sleep(5)` 间隔）
3. 超时上限 **5 分钟**，超时抛异常
4. 获取结果（JSONL 格式，每页一条记录，含 Markdown + 图片 URL）
5. 多页合并为一个 `.md` 文件，页间用 `<!-- Page N -->` 标注
6. 下载图片保存到输出目录

**Token 管理：**

- Token 存放位置：`~/.inkstone/.env`（全局生效，配一次即可）
- 环境变量名：`PADDLE_OCR_TOKEN`
- 仓库根目录提供 `.env.example` 作为模板
- Token 缺失时扫描版 PDF 直接报错，不做 fallback
- 使用 `python-dotenv` 加载 `.env` 文件

### 3.3 HTML 路线

```
HTML 输入（SingleFile 本地 HTML）
  │
  ├─ 1. 预处理（BeautifulSoup）
  │    → 遍历所有 <img> 标签
  │    → 提取 src 属性中的 base64 图片数据
  │    → 存为 report/img_001.png, img_002.png ...
  │    → 将 HTML 中的 base64 src 替换为本地文件名
  │    → 得到"瘦身 HTML"（从 ~10MB 缩减到几百 KB）
  │
  ├─ 2. Trafilatura 提取正文
  │    → 参数：include_images=True, include_tables=True,
  │            include_links=True, favor_recall=True,
  │            output_format="markdown"
  │    → 输出: Markdown 字符串
  │
  └─ 3. 写入输出目录
       → report/report.md + report/img_001.png ...
```

**必须用 BeautifulSoup 解析，不能用正则。** SingleFile HTML 中 `<img>` 标签的 src 属性引号不一致，正则只能匹配部分。

### 3.4 DOCX 路线（占位，暂不实现）

```
DOCX 输入
  │
  └─ python-docx 解析
       → 提取正文段落、标题层级、表格、列表
       → 转化为 Markdown
```

### 3.5 扫描版检测逻辑（detect.py）

仅用于 PDF 内部的扫描版/文字版判断，不做格式检测（格式由调用方传参）。

```python
import pymupdf

def is_scanned_pdf(path: str) -> bool:
    """检查 PDF 是否有可提取文字。采样前 3 页，任一页 >50 字符即为文字版。"""
    doc = pymupdf.open(path)
    for page in doc[:3]:
        text = page.get_text().strip()
        if len(text) > 50:
            return False
    return True
```

- 使用 PyMuPDF（`pymupdf` 包），毫秒级检测
- 采样前 3 页，任一页提取文字 >50 字符即判定为文字版
- 仅做检测，不做实际文本提取


## 4. 分发方式

### 4.1 三种入口，同一份代码

| 用户类型 | 安装方式 | 说明 |
|---------|---------|------|
| Python 开发者 | `pip install {org}-inkstone` | 纯库，import 直接用 |
| 任意 Agent 用户 | `pip install {org}-inkstone` + MCP 配置 | MCP Server |
| Claude Code 用户 | `npx skills add {org}/inkstone` | SKILL，渐进式披露 |

### 4.2 命名方案

```
GitHub:    {org}/inkstone
PyPI:      {org}-inkstone          ← 避开已被占用的 inkstone
npm scope: @{org}/inkstone         ← scope 隔离
CLI 命令:  inkstone                ← 本地命令行不冲突
import:    from inkstone import extract
```

### 4.3 MCP Server 配置

安装后，用户在 Agent 的 MCP 配置中添加：

```json
{
  "mcpServers": {
    "inkstone": {
      "command": "inkstone-mcp"
    }
  }
}
```

### 4.4 SKILL 安装（后续做）

```bash
npx skills add {org}/inkstone
```


## 5. MCP Server 设计

### 5.1 暴露的 Tool

保持最小化，**仅 1 个 tool**：

```json
{
  "name": "extract",
  "description": "将 HTML/PDF/DOCX 文件转化为结构化 Markdown。自动提取图片并保存为本地文件。返回输出目录路径。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "文件路径"
      },
      "format": {
        "type": "string",
        "enum": ["html", "pdf", "docx"],
        "description": "文件格式"
      }
    },
    "required": ["path", "format"]
  }
}
```

设计决策：
- 只暴露 1 个 tool，不暴露 `detect_type`、`extract_pdf` 等内部函数
- 不做 `batch_extract`：Agent 需要批量处理时连续调用单个 `extract` 即可
- `format` 由调用方传参，不做自动检测

### 5.2 传输方式

stdio（本地进程）。

### 5.3 实现

使用 **MCP Python SDK v2**（`mcp >= 2.0`，`MCPServer` 类，2026-07-28 规范）：

```python
from mcp.server import MCPServer

mcp = MCPServer("inkstone")

@mcp.tool()
def extract(path: str, format: str) -> str:
    """将 HTML/PDF/DOCX 文件转化为结构化 Markdown。
    自动提取图片并保存为本地文件。返回输出目录路径。"""
    from inkstone.core import extract as core_extract
    return core_extract(path, format=format)

def main():
    mcp.run(transport="stdio")
```

注意：MCP SDK v2 将 v1 的 `FastMCP`（`from mcp.server.fastmcp import FastMCP`）改名为 `MCPServer`（`from mcp.server import MCPServer`）。开发环境需安装 `mcp >= 2.0`。


## 6. SKILL 设计（后续做）

### 6.1 SKILL.md 结构

```markdown
---
name: inkstone
description: >
  当需要读取 PDF、DOCX、HTML 等非结构化文件并转化为结构化 Markdown 时使用。
  支持金融报表、研报、网页、公告等文档类型。自动识别 PDF 扫描版。
  调用 scripts/extract.py 处理，Agent 无需接触原始文件。
---

# Inkstone 文档结构化提取

## 使用方式

对任何需要读取的文件，执行：
\`\`\`bash
python {SKILL_DIR}/scripts/extract.py <文件路径> <格式>
\`\`\`

输出为 Markdown 文件 + 图片，可直接读取。
```

### 6.2 scripts/extract.py

```python
#!/usr/bin/env python3
import sys
from inkstone.core import extract

input_path = sys.argv[1]
format = sys.argv[2]
output_dir = extract(input_path, format=format)
print(f"提取完成: {output_dir}")
```


## 7. 仓库结构

```
{org}/inkstone/
│
├── pyproject.toml
├── README.md
├── LICENSE                             ← Apache 2.0
├── .env.example                        ← PADDLE_OCR_TOKEN= 模板
│
├── src/
│   └── inkstone/
│       ├── __init__.py                 ← from inkstone import extract
│       ├── core.py                     ← 统一入口 + 格式路由
│       ├── html.py                     ← 预处理 + Trafilatura 封装
│       ├── pdf.py                      ← Docling 封装 + 内部路由（调 detect + pdf_ocr）
│       ├── pdf_ocr.py                  ← PaddleOCR 云端 API 封装
│       ├── docx.py                     ← （占位，暂不实现）
│       ├── detect.py                   ← 扫描版检测（PyMuPDF，仅 PDF 内部使用）
│       └── mcp_server.py              ← MCP Server 入口
│
├── inkstone/                           ← SKILL 目录（后续做）
│   ├── SKILL.md
│   └── scripts/
│       └── extract.py
│
└── tests/
    ├── test_html.py
    ├── test_pdf.py                     ← Docling 文字版真实 fixture 测试
    └── fixtures/
        └── *.pdf                       ← 测试用 PDF（gitignore 排除）
```


## 8. pyproject.toml 关键配置

```toml
[project]
name = "{org}-inkstone"
version = "0.1.0"
description = "将 HTML/PDF/DOCX 转化为 AI Agent 可消费的结构化 Markdown"
requires-python = ">=3.10"
license = "Apache-2.0"

dependencies = [
    "trafilatura>=2.0",
    "beautifulsoup4>=4.12",
    "mcp>=2.0",
]

[project.optional-dependencies]
pdf = ["docling>=2.80", "pymupdf", "requests", "python-dotenv"]
docx = ["python-docx>=1.0"]

[project.scripts]
inkstone = "inkstone.core:cli_main"
inkstone-mcp = "inkstone.mcp_server:main"
```

设计决策：
- 只用 **uv** 作为包管理器开发
- PDF 依赖放在 optional-dependencies：Docling（提取）+ PyMuPDF（检测）+ requests（PaddleOCR API）+ python-dotenv（.env 加载）
- PaddleOCR 走云端 API，不再需要 `paddleocr` 和 `paddlepaddle` 本地依赖
- 分发走 PyPI


## 9. 不做的事情

明确排除，避免范围蔓延：

- **不做 URL 输入**：只接受本地文件路径
- **不做格式自动检测**：靠调用方传 `format` 参数
- **不做传参校验兜底**：格式传错直接报错
- **不做图片理解**：下游 Agent 是多模态模型，自己看图
- **不做 batch 接口**：Agent 需要批量处理时连续调用单个 `extract` 即可
- **不做缓存**：暂不需要
- **不做分块输出**：暂不需要
- **不做 OCR fallback**：Token 缺失时扫描版 PDF 直接报错


## 10. 未来扩展方向

- 更多格式支持：PPTX、XLSX、EPUB、纯文本
- 图片理解：对提取出的图片引用，可选调用多模态模型生成描述
- 缓存层：相同文件不重复提取，返回缓存结果
- 分块输出：对超长文档按章节/页码分块输出，适配 RAG 管线
