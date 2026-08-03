# Inkstone

> 砚——把粗糙的墨条研磨成可以直接书写的墨汁。
> Inkstone 把非结构化文档转化为 AI Agent 可直接消费的结构化 Markdown。

Inkstone 是一个面向 AI Agent 生态的文档结构化提取工具。Agent 调用一个接口，拿到干净的 Markdown + 图片文件，永远不碰原始文档。

## 支持格式

| 格式 | 状态 | 引擎 |
|------|------|------|
| HTML | ✅ | BeautifulSoup 预处理 + Trafilatura |
| PDF（文字版） | ✅ | Docling（TableFormer 表格识别 + 图片提取） |
| PDF（扫描版） | ✅ | PaddleOCR 云端 API（自动检测，无需手动指定） |
| DOCX | 🔜 | 占位，暂未实现 |

## 安装

```bash
# 基础安装（仅 HTML）
uv pip install inkstone

# 启用 PDF 支持
uv pip install inkstone[pdf]
```

没有 uv 的环境可以用 pip 替代：`pip install inkstone[pdf]`

### 开发环境

```bash
git clone <repo-url>
cd inkstone
uv sync --extra pdf
```

## 使用

### Python 库

```python
from inkstone import extract

# HTML
output_dir = extract("report.html", format="html")

# PDF（自动区分文字版/扫描版）
output_dir = extract("report.pdf", format="pdf")
```

输入 `report.pdf` → 输出 `report/` 目录：

```
report/
  report.md        ← 结构化 Markdown
  images/          ← 提取的图片（PDF）
    image_000000_xxx.png
    image_000001_xxx.png
```

### 命令行

```bash
inkstone extract report.pdf --format pdf
```

### MCP Server

Inkstone 提供 MCP Server，任何支持 MCP 的 Agent 都可以直接调用：

```json
{
  "mcpServers": {
    "inkstone": {
      "command": "inkstone-mcp"
    }
  }
}
```

暴露 1 个 tool：`extract(path, format)` → 返回输出目录路径。

## 配置

### PaddleOCR Token（仅扫描版 PDF 需要）

扫描版 PDF 使用 PaddleOCR 云端 API，需要配置 Token：

```bash
mkdir -p ~/.inkstone
echo "PADDLE_OCR_TOKEN=your_token_here" > ~/.inkstone/.env
```

文字版 PDF 不需要 Token。如果未配置 Token 且输入是扫描版 PDF，会直接报错。

## 设计原则

- **Agent 不碰原始文件**：所有清洗、提取都在代码层完成
- **统一输出**：无论输入什么格式，输出永远是 Markdown + 资源文件
- **信息零丢失**：宁可多保留噪音，不可误删内容（`favor_recall`）
- **不做图片理解**：下游 Agent 是多模态模型，Inkstone 只负责完整提取图片

## License

Apache-2.0
