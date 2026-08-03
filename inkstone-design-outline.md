# Inkstone 设计大纲

> 砚——把粗糙的墨条研磨成可以直接书写的墨汁。
> Inkstone 把非结构化文档转化为 AI Agent 可直接消费的结构化 Markdown。

---

## 1. 项目定位

Inkstone 是一个文档结构化提取工具，面向 AI Agent 生态设计。它解决的核心问题是：Agent 需要读取信源，但原始文档（PDF、DOCX、HTML）充满噪音，直接送入上下文会浪费 token 并干扰理解。

Inkstone 在代码层完成所有判断、路由和清洗，Agent 只需调用一个接口，拿到干净的 Markdown。Agent 永远不碰原始文件。

**设计原则：**

- Agent 不做判断：所有文件类型检测、扫描版识别、噪音过滤都在代码层完成
- 统一输出：无论输入什么格式，输出永远是 Markdown
- 信息零丢失：宁可多保留，不可误删（金融场景优先 recall）
- 跨 Agent 可用：同时提供 MCP Server 和 SKILL 两种接入方式


## 2. 架构总览

```
┌─────────────────────────────────────────────────┐
│                  Core Library                    │
│              pip install {org}-inkstone           │
│                                                  │
│  extract(path) → Markdown                        │
│                                                  │
│  ┌───────────┐ ┌───────────┐ ┌────────────────┐ │
│  │  pdf.py   │ │  docx.py  │ │   html.py      │ │
│  │  Docling   │ │ python-   │ │  Trafilatura   │ │
│  │  /Paddle   │ │ docx      │ │                │ │
│  │  OCR      │ │           │ │                │ │
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
def extract(path: str) -> str:
    """输入文件路径，返回结构化 Markdown。所有路由在内部完成。"""
    ext = detect_format(path)
    if ext == "pdf":
        return extract_pdf(path)
    elif ext == "docx":
        return extract_docx(path)
    elif ext == "html":
        return extract_html(path)
    else:
        raise UnsupportedFormatError(f"不支持的格式: {ext}")
```

### 3.2 PDF 路线

```
PDF 输入
  │
  ├─ detect.py 检测是否有文字层
  │
  ├─ 有文字层（文字版 PDF）
  │    → Docling（do_ocr=False, do_table_structure=True）
  │    → 输出 Markdown
  │
  └─ 无文字层（扫描版 PDF）
       → PaddleOCR
       → 输出 Markdown
```

**技术选型理由：**

- Docling（IBM，Apache 2.0）：内置 TableFormer 模型，金融表格处理最强；原生文字提取零幻觉；支持 XBRL 金融报告解析；商用无风险
- PaddleOCR：仅作为扫描版兜底；API 成本极低
- 关闭 OCR 后 Docling 在 x86 CPU 上约 1-2 秒/页，笔记本可用

**Docling 配置：**

```python
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions

opts = PdfPipelineOptions(
    do_ocr=False,
    do_table_structure=True,
)

converter = DocumentConverter(
    format_options={
        InputFormat.PDF: PdfFormatOption(pipeline_options=opts)
    }
)
```

### 3.3 HTML 路线

```
HTML 输入
  │
  └─ Trafilatura 统一处理
       参数：include_images=True（保留图片引用，金融图表不可丢）
             include_tables=True（保留表格）
             include_links=True（保留链接）
             favor_recall=True（金融场景宁可多抓）
             output_format="markdown"
  │
  └─ 输出 Markdown（含图片引用 ![alt](url)）
```

**说明：** 无需区分"干净 HTML"和"网页型 HTML"。Trafilatura 对两种输入都能正确处理：干净 HTML 近乎原样保留正文；嘈杂网页自动去除导航、广告、脚本等噪音。所有判断在 Trafilatura 内部完成，不依赖 Agent。

### 3.4 DOCX 路线

```
DOCX 输入
  │
  └─ python-docx 解析
       → 提取正文段落、标题层级、表格、列表
       → 转化为 Markdown
```

### 3.5 扫描版检测逻辑（detect.py）

```python
import pymupdf  # 仅用于检测，不用于提取

def is_scanned_pdf(path: str) -> bool:
    """检查 PDF 是否有可提取文字。在代码层完成，不进 Agent 上下文。"""
    doc = pymupdf.open(path)
    for page in doc[:3]:  # 采样前 3 页
        text = page.get_text().strip()
        if len(text) > 50:
            return False
    return True
```

**注意：** 此处使用 PyMuPDF 仅做文字层检测（几 ms 级别），不用于实际文本提取。实际提取走 Docling。PyMuPDF 的 AGPL 许可在"仅检测不分发"场景下需评估，或可替换为 pymupdf 的轻量替代（如 pypdf）进行检测。


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

### 4.4 SKILL 安装

```bash
npx skills add {org}/inkstone
```

安装后 Claude Code 自动识别。SKILL.md 的 description 控制在 1024 字符内，确保渐进式披露生效。


## 5. MCP Server 设计

### 5.1 暴露的 Tools

保持最小化，仅 2 个 tool，减少 token 压力：

**Tool 1: `extract`**

```json
{
  "name": "extract",
  "description": "将 PDF/DOCX/HTML 文件转化为结构化 Markdown。自动识别文件类型和 PDF 扫描版。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "path": {
        "type": "string",
        "description": "文件路径"
      }
    },
    "required": ["path"]
  }
}
```

**Tool 2: `batch_extract`**

```json
{
  "name": "batch_extract",
  "description": "批量提取多个文件，返回各文件的 Markdown。",
  "inputSchema": {
    "type": "object",
    "properties": {
      "paths": {
        "type": "array",
        "items": { "type": "string" },
        "description": "文件路径列表"
      }
    },
    "required": ["paths"]
  }
}
```

**设计考量：** 只暴露 2 个 tool，大约 500-800 tokens 的 schema 开销。不暴露 detect_type、extract_pdf 等内部函数——Agent 不需要知道内部路由，这是 Inkstone 的职责。

### 5.2 传输方式

优先 stdio（本地进程）。这是受 MCP 2026-07-28 协议更新影响最小的路径，且官方 SDK 内置了新旧协议的自动协商。

### 5.3 实现基础

使用 MCP Python SDK（官方 Tier 1），已支持 2026-07-28 规范：

```python
from mcp.server import Server

server = Server("inkstone")

@server.tool()
async def extract(path: str) -> str:
    """将 PDF/DOCX/HTML 文件转化为结构化 Markdown"""
    from inkstone.core import extract as core_extract
    return core_extract(path)
```


## 6. SKILL 设计

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
python {SKILL_DIR}/scripts/extract.py <文件路径> <输出路径>
\`\`\`

输出为 Markdown 文件，可直接读取。

## 支持格式

- PDF（自动区分文字版/扫描版）
- DOCX
- HTML（自动去除导航、广告等噪音，保留正文、表格、图片引用）

## 首次使用

\`\`\`bash
pip install {org}-inkstone
\`\`\`

## 注意事项

- 不要直接读取原始 PDF/HTML，总是通过本 SKILL 提取后再读取
- 输出固定为 Markdown，所有格式判断在工具内部完成
- 金融图表以 ![alt](url) 形式保留在 Markdown 中
```

### 6.2 scripts/extract.py

SKILL 内的脚本作为 CLI 入口，调用核心库：

```python
#!/usr/bin/env python3
"""Inkstone SKILL 脚本入口。Agent 调用此脚本，代码不进入上下文。"""
import sys
from inkstone.core import extract

input_path = sys.argv[1]
output_path = sys.argv[2]

result = extract(input_path)

with open(output_path, "w", encoding="utf-8") as f:
    f.write(result)

print(f"提取完成: {output_path}")
```


## 7. 仓库结构

```
{org}/inkstone/
│
├── pyproject.toml                      ← Python 包定义
├── README.md                           ← 安装说明（人读）
├── LICENSE                             ← Apache 2.0
│
├── src/
│   └── inkstone/
│       ├── __init__.py                 ← from inkstone import extract
│       ├── core.py                     ← 统一入口 + 格式路由
│       ├── pdf.py                      ← Docling 封装
│       ├── pdf_ocr.py                  ← PaddleOCR 封装（扫描版兜底）
│       ├── docx.py                     ← python-docx 解析
│       ├── html.py                     ← Trafilatura 封装
│       ├── detect.py                   ← 扫描版检测 + 格式检测
│       └── mcp_server.py              ← MCP Server 入口
│
├── inkstone/                           ← SKILL 目录（npx skills add 识别）
│   ├── SKILL.md
│   └── scripts/
│       └── extract.py
│
├── tests/
│   ├── test_pdf.py
│   ├── test_html.py
│   ├── test_docx.py
│   └── fixtures/                       ← 测试用文档样本
│
└── scripts/
    └── install.sh                      ← 一键安装脚本（检测环境，配置 MCP + SKILL）
```


## 8. pyproject.toml 关键配置

```toml
[project]
name = "{org}-inkstone"
version = "0.1.0"
description = "将 PDF/DOCX/HTML 转化为 AI Agent 可消费的结构化 Markdown"
requires-python = ">=3.10"
license = "Apache-2.0"

dependencies = [
    "docling>=2.80",
    "trafilatura>=2.0",
    "python-docx>=1.0",
    "mcp>=2.0",
]

[project.optional-dependencies]
ocr = ["paddleocr>=2.8", "paddlepaddle>=2.6"]

[project.scripts]
inkstone = "inkstone.core:cli_main"
inkstone-mcp = "inkstone.mcp_server:main"
```

**说明：** PaddleOCR 放在 optional dependencies 中（`pip install {org}-inkstone[ocr]`）。大部分用户处理文字版 PDF 不需要它，避免安装 PaddlePaddle 这个重依赖。


## 9. 版本与发布

- 语义化版本：v0.1.0 → v0.2.0（新格式支持）→ v1.0.0（生产稳定）
- GitHub Release + Tag：`npx skills add` 可锁定版本
- PyPI 发布：每个 tag 自动触发 CI 发布
- SKILL 和 MCP Server 同版本号，同仓库，同 tag


## 10. 未来扩展方向

- 更多格式支持：PPTX、XLSX、EPUB、纯文本
- 图片理解：对提取出的图片引用，可选调用多模态模型生成描述
- 缓存层：相同文件不重复提取，返回缓存结果
- 分块输出：对超长文档按章节/页码分块输出，适配 RAG 管线
- XBRL 深度解析：利用 Docling 的 XBRL 能力，结构化提取财务数据
