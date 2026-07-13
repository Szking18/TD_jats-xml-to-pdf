import xml.etree.ElementTree as ET

# 读取XML文件（假设你把那个样例存成了 sample.xml）
tree = ET.parse('初始文件.xml')
root = tree.getroot()


# 提取标题
title_elem = root.find('.//article-title')
title = title_elem.text if title_elem is not None else "未找到标题"
print(f"标题: {title}")

# 提取所有作者
authors = []
for author in root.findall('.//contrib'):
    surname = author.find('.//surname')
    given = author.find('.//given-names')
    if surname is not None and given is not None:
        authors.append(f"{given.text} {surname.text}")
print(f"作者: {', '.join(authors)}")

# 提取摘要全文
abstract_parts = []
for p in root.findall('.//abstract//p'):
    if p.text:
        abstract_parts.append(p.text)
abstract = ' '.join(abstract_parts)
print(f"摘要长度: {len(abstract)} 字符")
print(f"摘要预览: {abstract[:200]}...")