---
name: inkstone
description: >
  当需要读取 PDF、HTML、DOCX 等非结构化文件并转化为结构化 Markdown 时使用。
  支持金融研报、网页文章、公告等文档类型。PDF 自动区分文字版和扫描版。
  调用 scripts/extract.py 处理，Agent 无需接触原始文件。
---

# Inkstone 文档结构化提取

将 PDF、HTML、DOCX 等非结构化文件转化为 AI 可直接消费的 Markdown + 图片。

## 使用方式

用 `uv run` 一条命令完成依赖安装和提取，无需手动管理环境：

```bash
uv run --directory "{SKILL_DIR}/.." python "{SKILL_DIR}/scripts/extract.py" <文件路径>
```

- 格式从文件扩展名自动推断（`.pdf`→pdf、`.html`/`.htm`→html、`.docx`→docx）
- 输出目录与输入文件同级（如 `report.pdf` → `report/report.md` + 图片）
- 命令输出为输出目录路径

### 示例

```bash
# 提取 PDF 研报
uv run --directory "{SKILL_DIR}/.." python "{SKILL_DIR}/scripts/extract.py" "/path/to/研报.pdf"

# 提取 HTML 网页
uv run --directory "{SKILL_DIR}/.." python "{SKILL_DIR}/scripts/extract.py" "/path/to/article.html"
```

然后读取输出目录中的 `.md` 文件即可。

## 禁止事项

- **不要**直接调用 `python` 或 `.venv/Scripts/python` 或 `.venv/bin/python`，必须通过 `uv run` 执行
- **不要**手动运行 `pip install`、`uv pip install` 或任何包安装命令
- **不要**直接读取原始 PDF/HTML/DOCX，总是通过本 SKILL 提取后再读取

## 支持格式

- **PDF**：自动区分文字版（Docling 提取）和扫描版（PaddleOCR 云端 OCR）。文字版支持表格结构识别和图片提取。
- **HTML**：自动去除导航、广告等噪音，保留正文、表格、图片引用。适用于 SingleFile 保存的网页。
- **DOCX**：Pandoc 转换，完整保留标题层级、表格、脚注、图片。

## 扫描版 PDF 配置

扫描版 PDF 需要额外配置 PaddleOCR Token：

```bash
mkdir -p ~/.inkstone
echo "PADDLE_OCR_TOKEN=<your_token>" > ~/.inkstone/.env
```

## 注意事项

- 输出固定为 Markdown，所有格式判断在工具内部完成
- 图片以 `![](path)` 形式保留在 Markdown 中，可直接查看
