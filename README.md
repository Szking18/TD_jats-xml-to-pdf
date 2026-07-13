# JATS XML → PDF 智能排版引擎

学术期刊创新大赛 · 选题二：面向学术出版的智能排版引擎研究

## 功能

将 JATS 1.3 格式的学术论文 XML 自动转换为高质量双栏 PDF，支持：

- ✅ 标题、作者、摘要、关键词的正确渲染
- ✅ 正文段落与章节结构的流式双栏排版
- ✅ 图片、表格的自动编号与交叉引用
- ✅ 数学公式（MathML格式）的高保真 SVG 渲染
- ✅ 参考文献的格式化输出
- ✅ 双栏排版的灵活切换
- ✅ 页眉页脚、页码的自动生成

## 技术栈

| 组件 | 技术 |
|------|------|
| PDF 引擎 | WeasyPrint 69 |
| XML 解析 | lxml |
| 模板引擎 | Jinja2 |
| 公式渲染 | MathJax (Node.js) |
| 排版 | CSS Paged Media |

## 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
npm install mathjax-full
```

### 生成 PDF

```bash
python generate_pdf.py 初始文件.xml
python generate_pdf.py input.xml output.pdf --debug
```

### 批量测试

```bash
python run_all.py
```

## 文件结构

```
├── jats_parser.py         # JATS XML 完整解析器
├── mathml_renderer.py     # MathML→SVG 渲染模块 (Python)
├── mathjax_render.js      # MathML→SVG 渲染脚本 (Node.js)
├── html_renderer.py       # Jinja2 HTML 渲染器
├── templates/
│   └── article.html       # Jinja2 文章模板
├── style.css              # 双栏学术期刊 CSS
├── generate_pdf.py        # 主入口
├── run_all.py             # 批量测试脚本
├── requirements.txt       # Python 依赖
└── package.json           # Node.js 依赖
```

## 核心功能要求对照

| 竞赛要求 | 实现状态 |
|----------|---------|
| 标题、作者、摘要、关键词正确渲染 | ✅ |
| 正文段落与章节结构流式排版 | ✅ |
| 图片、表格自动编号与交叉引用 | ✅ |
| MathML 公式高保真渲染 | ✅ |
| 参考文献格式化输出 | ✅ |
| 多栏排版灵活切换 | ✅ |
| 页眉页脚页码自动生成 | ✅ |
