# Knowledge Base Directory

这个目录用于存放“知识库原始数据”，和 `app/configs` 中的运行策略配置分离。

推荐约定：

- `school_articles.json`
  存放院校考情文章数据
- `experience_albums.json`
  存放经验专辑数据
- `summary_albums.json`
  存放总表/汇总专辑数据
- `raw/`
  存放暂未清洗的原始文档或抓取结果

建议原则：

1. `data/kb` 放知识内容本身
2. `app/configs` 放关键词、模板、导流文案等策略
3. `app/src/repository.py` 负责读取这里的数据

## 示例数据结构

### school_articles.json

```json
[
  {
    "school": "华中科技大学",
    "year": 2025,
    "title": "华中科技大学 2025 年计算机考研考情分析",
    "source": "school/hust/2025",
    "url": "https://example.com/hust-2025"
  }
]
```

### experience_albums.json

```json
[
  {
    "title": "考研经验专辑 1",
    "source": "album/experience-1",
    "url": "https://example.com/experience-1"
  }
]
```

### summary_albums.json

```json
[
  {
    "title": "25 考情分析总表专辑",
    "source": "album/summary-2025",
    "url": "https://example.com/summary-2025"
  }
]
```
