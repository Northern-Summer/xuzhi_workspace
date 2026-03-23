---
name: "multi-search-engine"
description: "Multi search engine integration with 17 engines (8 CN + 9 Global) + local SearXNG. Zero API cost when using local SearXNG."
---

# Multi Search Engine v2.1

## 本地 SearXNG（优先使用，零 API 消耗）

**地址**: `http://127.0.0.1:8080`（Docker Desktop 上 SearXNG）

**优势**: 零 API 消耗、JSON 结构化返回、可多引擎聚合

**使用方法**:
```bash
python3 ~/.openclaw/workspace/skills/multi-search-engine/searxng_client.py "<搜索词>" [引擎]
# 例: python3 searxng_client.py "hello world" bing,ddg
```

**可用引擎**: bing, ddg, google, wikipedia, qwant, brave, startpage

**API 调用**（程序内使用）:
```python
import sys
sys.path.insert(0, "~/.openclaw/workspace/skills/multi-search-engine")
from searxng_client import search

result = search("搜索词", engines=["bing", "ddg"], max_results=10)
for r in result["results"]:
    print(r["title"], r["url"], r["snippet"])
```

**限制**: 
- Google/DDG/Startpage 等被墙引擎需要 Clash Verge 代理
- Wikipedia 引擎在当前配置下返回 0 条（需进一步调试）

---

## 旧版 web_fetch（备用）

当 SearXNG 不可用时，使用以下 URL 模板 + web_fetch 工具。

### Domestic (8)
- **Baidu**: `https://www.baidu.com/s?wd={keyword}`
- **Bing CN**: `https://cn.bing.com/search?q={keyword}&ensearch=0`
- **Bing INT**: `https://cn.bing.com/search?q={keyword}&ensearch=1`
- **360**: `https://www.so.com/s?q={keyword}`
- **Sogou**: `https://sogou.com/web?query={keyword}`
- **WeChat**: `https://wx.sogou.com/weixin?type=2&query={keyword}`
- **Toutiao**: `https://so.toutiao.com/search?keyword={keyword}`
- **Jisilu**: `https://www.jisilu.cn/explore/?keyword={keyword}`

### International (9)
- **Google**: `https://www.google.com/search?q={keyword}`
- **Google HK**: `https://www.google.com.hk/search?q={keyword}`
- **DuckDuckGo**: `https://duckduckgo.com/html/?q={keyword}`
- **Yahoo**: `https://search.yahoo.com/search?p={keyword}`
- **Startpage**: `https://www.startpage.com/sp/search?query={keyword}`
- **Brave**: `https://search.brave.com/search?q={keyword}`
- **Ecosia**: `https://www.ecosia.org/search?q={keyword}`
- **Qwant**: `https://www.qwant.com/?q={keyword}`
- **WolframAlpha**: `https://www.wolframalpha.com/input?i={keyword}`

## Advanced Operators

| Operator | Example | Description |
|----------|---------|-------------|
| `site:` | `site:github.com python` | Search within site |
| `filetype:` | `filetype:pdf report` | Specific file type |
| `""` | `"machine learning"` | Exact match |
| `-` | `python -snake` | Exclude term |
| `OR` | `cat OR dog` | Either term |

## Time Filters

| Parameter | Description |
|-----------|-------------|
| `tbs=qdr:h` | Past hour |
| `tbs=qdr:d` | Past day |
| `tbs=qdr:w` | Past week |
| `tbs=qdr:m` | Past month |
| `tbs=qdr:y` | Past year |

## Documentation

- `references/advanced-search.md` - Domestic search guide
- `references/international-search.md` - International search guide
- `CHANGELOG.md` - Version history

## License

MIT
