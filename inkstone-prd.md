# Inkstone HTML 模块 PRD

> 砚——把粗糙的墨条研磨成可以直接书写的墨汁。
> Inkstone 把非结构化文档转化为 AI Agent 可直接消费的结构化 Markdown。

本文档是 Inkstone 项目 HTML 模块的落地 PRD。所有设计决策均经过逐条审查确认。新 Claude 实例可直接依据本文档开始编码。

---

## 1. 项目定位

Inkstone 是一个文档结构化提取工具，面向 AI Agent 生态设计。Agent 调用一个接口，拿到干净的 Markdown + 图片文件。Agent 永远不碰原始文件内容。

**设计原则：**

- Agent 不碰原始文件内容：所有清洗、提取都在代码层完成
- 统一输出：无论输入什么格式，输出永远是 Markdown + 资源文件
- 信息零丢失：宁可多保留噪音，不可误删内容（`favor_recall`）
- 下游 Agent 是多模态模型：Inkstone 不做图片理解，只负责完整提取图片

## 2. 当前范围

**只实现 HTML 路线。** 架构按三种格式设计（HTML/PDF/DOCX），但本阶段只写 HTML 的实际处理逻辑，其他格式留接口占位。

## 3. 输入假设

- 输入是 **本地 HTML 文件**，由人工使用 **SingleFile** 浏览器扩展保存
- SingleFile 产出的 HTML 是完整的单文件快照：所有资源（CSS、图片、字体）内联为 data URI，DOM 是浏览器渲染后的最终状态
- 典型文件大小：5-10MB
- 典型内容类型：新闻文章、金融研报网页版、微信公众号文章
- 人工保存时会滚动到页面底部，确保懒加载图片全部加载

## 4. HTML 处理流程

```
输入: report.html (SingleFile 本地 HTML)
  │
  ├─ 1. 预处理（BeautifulSoup）
  │    → 遍历所有 <img> 标签
  │    → 提取 src 属性中的 base64 图片数据
  │    → 存为 report/img_001.png, img_002.png ...
  │    → 将 HTML 中的 base64 src 替换为本地文件名
  │    → 得到"瘦身 HTML"（从 ~10MB 缩减到几百 KB）
  │
  ├─ 2. Trafilatura 提取正文
  │    → 输入: 瘦身后的 HTML 字符串
  │    → 参数:
  │         include_images=True
  │         include_tables=True
  │         include_links=True
  │         favor_recall=True
  │         output_format="markdown"
  │    → 输出: Markdown 字符串
  │
  └─ 3. 写入输出目录
       → report/report.md
       → report/img_001.png
       → report/img_002.png
       → ...

输出目录: report/（与输入文件同级目录）
```

### 4.1 预处理关键细节

**必须用 BeautifulSoup 解析，不能用正则。** 原因：SingleFile 保存的 HTML 中，`<img>` 标签的 src 属性有的带双引号、有的带单引号、有的不带引号。正则 `src="data:image/[^"]*"` 只能匹配双引号的情况，实测会漏掉约一半的正文图片。

实测数据（华尔街见闻金融研报页面）：
- HTML 中共 38 处 `data:image/` 出现
- 其中 16 处在 `src="..."` 双引号属性中（正则能抓到）
- 其余 22 处在无引号的 `src=data:image/...` 中（正则抓不到）
- 用 BeautifulSoup 遍历 `<img>` 标签可以统一处理所有情况

预处理逻辑：
1. 用 BeautifulSoup 解析 HTML
2. 遍历所有 `<img>` 标签
3. 对每个 `<img>`，检查 src 属性是否以 `data:image/` 开头
4. 如果是，解码 base64 数据，写入图片文件（根据 MIME 类型决定扩展名）
5. 将 src 属性替换为本地文件名（如 `img_001.png`）
6. 返回修改后的 HTML 字符串

### 4.2 Trafilatura 行为备注

实测验证结果：
- Trafilatura **会丢弃所有 base64 data URI 图片**（即使设置了 `include_images=True`）—— 所以预处理是必须的，不是优化
- 预处理替换为本地路径后，Trafilatura **能正确保留本地路径的图片引用**（输出为 `![](img_001.png)` 格式）
- Trafilatura 能正确区分正文图片和非正文图片（二维码、页面装饰等被正确丢弃，正文图表全部保留）
- 图表标题与图片的关联由 Trafilatura 自动处理，不需要额外逻辑；如果关联不完美，交给下游 Agent 自行判断
- 样式信息（颜色、字号）丢失是可接受的，因为最终是喂给 LLM
- 文末噪音（"阅读原文"、"点赞在看"等）切不干净的话也可接受，LLM 能理解

## 5. 接口设计

### 5.1 核心函数

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

### 5.2 MCP Server

唯一暴露的 tool：

```python
from mcp.server import MCPServer

mcp = MCPServer("inkstone")

@mcp.tool()
def extract(path: str, format: str) -> str:
    """将 HTML/PDF/DOCX 文件转化为结构化 Markdown。
    自动提取图片并保存为本地文件。返回输出目录路径。"""
    from inkstone.core import extract as core_extract
    return core_extract(path, format=format)
```

MCP 协议要点：
- 使用 **MCP Python SDK v2**（`mcp` >= 2.0，`MCPServer` 类，非旧版 `FastMCP` 或 `Server`）
- 遵循 **2026-07-28 规范**（无状态，无 session 握手）
- 传输方式：**stdio**（本地进程，Claude Code 等本地 Agent 直接调用）
- 只暴露 1 个 tool，不暴露内部函数（`detect_type`、`extract_html` 等）
- 不做 `batch_extract`

用户安装后的 MCP 配置：

```json
{
  "mcpServers": {
    "inkstone": {
      "command": "inkstone-mcp"
    }
  }
}
```

### 5.3 SKILL（后续做）

SKILL 是独立于 MCP 的另一条入口，本质是一套提示词 + CLI 脚本。任何能跑 bash 的 Agent 都能用，不需要 MCP 能力。优先级低于 MCP，但架构上要预留。

SKILL 入口脚本调用同一个核心库：

```bash
python scripts/extract.py <文件路径> <格式>
```

## 6. 仓库结构

```
{org}/inkstone/
│
├── pyproject.toml
├── README.md
├── LICENSE                             ← Apache 2.0
│
├── src/
│   └── inkstone/
│       ├── __init__.py                 ← from inkstone import extract
│       ├── core.py                     ← 统一入口 + 格式路由
│       ├── html.py                     ← 预处理 + Trafilatura 封装
│       ├── pdf.py                      ← （占位，暂不实现）
│       ├── pdf_ocr.py                  ← （占位，暂不实现）
│       ├── docx.py                     ← （占位，暂不实现）
│       ├── detect.py                   ← （占位，暂不实现）
│       └── mcp_server.py              ← MCP Server 入口
│
├── inkstone/                           ← SKILL 目录（后续做）
│   ├── SKILL.md
│   └── scripts/
│       └── extract.py
│
└── tests/
    ├── test_html.py
    └── fixtures/
```

## 7. 依赖

```toml
[project]
name = "{org}-inkstone"
version = "0.1.0"
requires-python = ">=3.10"
license = "Apache-2.0"

dependencies = [
    "trafilatura>=2.0",
    "beautifulsoup4>=4.12",
    "mcp>=2.0",
]

[project.optional-dependencies]
pdf = ["docling>=2.80"]
ocr = ["paddleocr>=2.8", "paddlepaddle>=2.6"]
docx = ["python-docx>=1.0"]

[project.scripts]
inkstone = "inkstone.core:cli_main"
inkstone-mcp = "inkstone.mcp_server:main"
```

设计决策：
- 只用 **uv** 作为包管理器开发
- PDF/OCR/DOCX 依赖放在 optional-dependencies，HTML 路线不需要它们
- 分发走 PyPI

## 8. 不做的事情

明确排除，避免范围蔓延：

- **不做 URL 输入**：只接受本地文件路径
- **不做格式自动检测**：靠调用方传 `format` 参数
- **不做传参校验兜底**：格式传错直接报错
- **不做图片理解**：下游 Agent 是多模态模型，自己看图
- **不做表格特殊处理**：实际场景中 HTML 表格极少，大多数数据以图片形式存在
- **不做 batch 接口**：Agent 需要批量处理时连续调用单个 `extract` 即可
- **不做缓存**：暂不需要
- **不做分块输出**：暂不需要

## 9. 编码注意事项

给实现者的提醒：

1. **BeautifulSoup 解析时指定 `html.parser`**，不要依赖 lxml（减少额外依赖）
2. **图片文件命名**用递增编号 `img_001.png`、`img_002.png`，根据 base64 的 MIME 类型决定扩展名
3. **输出目录命名**取输入文件名去掉扩展名（如 `report.html` → `report/`）
4. **如果输出目录已存在**，直接覆盖写入（不清空，只覆盖同名文件）
5. **Markdown 文件编码**统一 UTF-8
6. **MCP Server 的 `main()` 函数**要能被 `inkstone-mcp` 命令行入口调用
7. **core.py 的 `cli_main()`** 要支持命令行直接调用：`inkstone extract report.html --format html`
