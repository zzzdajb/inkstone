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
