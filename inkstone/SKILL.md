---
name: inkstone
description: >
  当需要读取 PDF、HTML 等非结构化文件并转化为结构化 Markdown 时使用。
  支持金融研报、网页文章、公告等文档类型。PDF 自动区分文字版和扫描版。
  调用 scripts/extract.py 处理，Agent 无需接触原始文件。
---

# Inkstone 文档结构化提取

将 PDF、HTML 等非结构化文件转化为 AI 可直接消费的 Markdown + 图片。

## 使用方式

对任何需要读取的非结构化文件，执行：

```bash
python {SKILL_DIR}/scripts/extract.py <文件路径> <格式>
```

- `<格式>` 可选值：`html`、`pdf`、`docx`
- 输出目录与输入文件同级（如 `report.pdf` → `report/report.md` + 图片）
- 命令输出为输出目录路径

### 示例

```bash
# 提取 PDF 研报
python {SKILL_DIR}/scripts/extract.py "/path/to/研报.pdf" pdf

# 提取 HTML 网页
python {SKILL_DIR}/scripts/extract.py "/path/to/article.html" html
```

然后读取输出目录中的 `.md` 文件即可。

## 支持格式

- **PDF**：自动区分文字版（Docling 提取）和扫描版（PaddleOCR 云端 OCR）。文字版支持表格结构识别和图片提取。
- **HTML**：自动去除导航、广告等噪音，保留正文、表格、图片引用。适用于 SingleFile 保存的网页。

## 首次使用

```bash
pip install inkstone        # 基础安装（仅 HTML）
pip install inkstone[pdf]   # 启用 PDF 支持
```

扫描版 PDF 需要配置 PaddleOCR Token：

```bash
mkdir -p ~/.inkstone
echo "PADDLE_OCR_TOKEN=<your_token>" > ~/.inkstone/.env
```

## 注意事项

- 不要直接读取原始 PDF/HTML，总是通过本 SKILL 提取后再读取
- 输出固定为 Markdown，所有格式判断在工具内部完成
- 图片以 `![](path)` 形式保留在 Markdown 中，可直接查看
