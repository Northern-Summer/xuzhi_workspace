#!/usr/bin/env python3
"""
library_processor.py — 图书馆文献处理器 v3（正确设计）

问题本质（类型错误，不是内容问题）：
1. GBK编码被当作UTF-8 → 乱码实体
2. 没有句子切分 → 整段文本当作一个实体

解决方案（只修类型错误，不评判内容）：
- 编码自适应（GB18030/GBK/UTF-8）
- 句子级切分
- 实体质量过滤（拒绝乱码/乱码片段）
- 图书馆全面接入，不分内容类型

用法：
  python3 library_processor.py --preview   # 预览前3个文件的处理效果
  python3 library_processor.py --all       # 处理全部library文件
"""

import re, sqlite3
from pathlib import Path
from datetime import datetime

# ── 编码自适应 ────────────────────────────────────────────────

def detect_and_decode(raw: bytes) -> str:
    """智能解码：GB18030 > GBK > UTF-8"""
    for enc in ("gb18030", "gbk", "utf-8"):
        try:
            return raw.decode(enc, errors="strict")
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def extract_meta(content: str) -> dict:
    meta = {}
    m = re.search(r"<!--\s*(.*?)\s*-->", content, re.DOTALL)
    if m:
        for line in m.group(1).split("\n"):
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip()
    return meta


# ── 句子切分 ────────────────────────────────────────────────

def split_sentences(text: str) -> list:
    """按句子标点切分"""
    # 先清理章节注释
    text = re.sub(r'/\*\s*\d+\s*\*/', '', text)
    # 按段落
    blocks = re.split(r'\n\s*\n', text)
    sentences = []
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        # 按句子末标点切分
        parts = re.split(r'(?<=[。！？.!?])\s*', block)
        for s in parts:
            s = s.strip()
            if s:
                sentences.append(s)
    return sentences


# ── 实体质量过滤（核心：只修类型错误，不评判内容）─────────────

# 检测是否为乱码字符（编码错误特征）
GARBAGE_CHARS = set('ʣҪβðԵˣΪʲôҪðκأΪǸضڷǣǲ뱻š')

def is_garbage(sentence: str) -> bool:
    """
    判断句子是否为乱码。
    乱码特征：包含大量 Unicode 混合脚本字符（如希腊语+西里尔语+中文混合）
    这是编码错误的证据，不是内容歧视。
    """
    if not sentence:
        return True
    # 统计字符脚本多样性（正常文本通常只有1-2种脚本）
    # 乱码：同时包含 Greek+Cyrillic+Chinese ≈ 3种以上
    has_cyrillic = any('\u0400' <= c <= '\u04FF' for c in sentence)
    has_greek = any('\u0370' <= c <= '\u03FF' for c in sentence)
    has_chinese = any('\u4e00' <= c <= '\u9FFF' for c in sentence)
    script_count = sum([has_cyrillic, has_greek, has_chinese])
    # 乱码通常同时包含这三种
    if script_count >= 2 and has_cyrillic and has_greek:
        return True
    # 检测已知乱码片段
    if any(c in sentence for c in GARBAGE_CHARS):
        return True
    return False


def is_meaningful(sentence: str) -> bool:
    """
    判断句子是否有意义（结构化知识，而非噪声）。
    标准：长度合理 + 含有实际文字（非纯标点/数字）
    """
    if not sentence or len(sentence) < 8 or len(sentence) > 600:
        return False
    # 纯标点/数字过滤
    non_punct = sum(1 for c in sentence
                    if not c in "，。、：；「」『』（）【】()[]{}.,!?;:\"' \t\n-–—0123456789")
    if non_punct < 5:
        return False
    return True


# ── 实体提取 ────────────────────────────────────────────────

def extract_entities(sentence: str) -> list:
    """从句子提取命名实体（轻量正则，无LLM依赖）"""
    entities = []

    # 书名： 《》「」之间
    for m in re.finditer(r'[《「『]([^》」』]{2,30})[》」』]', sentence):
        entities.append((m.group(1), "book"))

    # 组织机构
    ORG_KW = ["大学", "学院", "公司", "医院", "研究所", "出版社",
              "基金会", "委员会", "实验室", "中心", "局", "部", "厅", "署"]
    for kw in ORG_KW:
        for m in re.finditer(rf'([\u4e00-\u9fff]{{2,12}}{kw})', sentence):
            entities.append((m.group(1), "organization"))

    # 人名（说话句式前面2-4字）
    for m in re.finditer(r'([\u4e00-\u9fff]{2,4})[说问道认为指出发现提出]', sentence):
        name = m.group(1)
        if len(name) >= 2:
            entities.append((name, "person"))

    # 专有名词（带引号/大写的词）
    for m in re.finditer(r'"([^"]{2,30})"', sentence):
        entities.append((m.group(1), "concept"))
    for m in re.finditer(r"'([^']{2,30})'", sentence):
        entities.append((m.group(1), "concept"))

    return entities


# ── 数据库 ────────────────────────────────────────────────

DB = Path.home() / "xuzhi_genesis/centers/intelligence/knowledge/knowledge.db"


def insert_entity(name, etype, source):
    """幂等插入，返回entity_id"""
    conn = sqlite3.connect(str(DB))
    conn.execute("PRAGMA foreign_keys=OFF")
    existing = conn.execute(
        "SELECT id FROM entities WHERE name=? COLLATE NOCASE LIMIT 1", (name,)
    ).fetchone()
    if existing:
        conn.close()
        return existing[0]
    eid = f"{abs(hash(name+source)) & 0xFFFFFFFF:08x}"[:16]
    now = datetime.now().isoformat()
    conn.execute("""INSERT OR IGNORE INTO entities
        (id,name,type,source,first_seen,last_seen,confidence,source_seed)
        VALUES (?,?,?,?,?,?,?,?)""",
        (eid, name, etype, source, now, now, 0.6, source))
    conn.commit()
    conn.close()
    return eid


def insert_rel(sid, pred, oid, source, causal=False):
    conn = sqlite3.connect(str(DB))
    conn.execute("PRAGMA foreign_keys=OFF")
    exists = conn.execute(
        "SELECT 1 FROM relations WHERE subject_id=? AND predicate=? AND object_id=? LIMIT 1",
        (sid, pred, oid)).fetchone()
    if not exists:
        rid = f"{abs(hash(sid+pred+oid)) & 0xFFFFFFFF:08x}"[:16]
        now = datetime.now().isoformat()
        conn.execute("""INSERT OR IGNORE INTO relations
            (id,subject_id,predicate,object_id,source,first_seen,last_seen,confidence,source_seed,is_causal)
            VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (rid, sid, pred, oid, source, now, now, 0.6, source, 1 if causal else 0))
        conn.commit()
    conn.close()


# ── 主处理 ────────────────────────────────────────────────

CAUSAL_PAT = re.compile(
    r"(?:导致|引发|使得|造成|引起|产生|由于|因为|因此|所以|"
    r"表明|证明|决定|影响|改变|创造|形成|建立|实现|揭示|说明|"
    r"causes|leads to|results in|triggers|increases|decreases|enables)",
    re.UNICODE
)


def process_file(filepath: Path, dry_run: bool = False) -> dict:
    stats = {
        "file": filepath.name,
        "encoding_detected": "unknown",
        "sentences_total": 0,
        "sentences_garbage": 0,
        "sentences_meaningful": 0,
        "entities_extracted": 0,
        "relations_extracted": 0,
        "causal_sents": 0,
        "errors": [],
        "preview": [],
    }

    try:
        raw = open(filepath, "rb").read()
    except Exception as e:
        stats["errors"].append(str(e))
        return stats

    # 编码检测
    text = detect_and_decode(raw)
    # 判断使用了哪种编码（通过检查乱码比例）
    if is_garbage(text[:200]):
        stats["encoding_detected"] = "GB18030→乱码（需重处理）"
    else:
        stats["encoding_detected"] = "正常文本"

    meta = extract_meta(text)
    source = meta.get("source", filepath.name)

    # 清理元数据头
    text = re.sub(r"<!--.*?-->\s*", "", text, flags=re.DOTALL).strip()
    sentences = split_sentences(text)
    stats["sentences_total"] = len(sentences)

    meaningful = []
    for s in sentences:
        if is_garbage(s):
            stats["sentences_garbage"] += 1
            continue
        if not is_meaningful(s):
            continue
        meaningful.append(s)
        stats["sentences_meaningful"] += 1

    stats["preview"] = meaningful[:8]

    if dry_run:
        return stats

    # 写入数据库
    for sent in meaningful:
        causal = bool(CAUSAL_PAT.search(sent))
        if causal:
            stats["causal_sents"] += 1
        entities = extract_entities(sent)
        eids = {}
        for name, etype in entities:
            eid = insert_entity(name, etype, filepath.name)
            eids[name] = eid
            stats["entities_extracted"] += 1
        # 共现关系
        elist = list(eids.items())
        for i in range(len(elist)):
            for j in range(i+1, len(elist)):
                _, id_i = elist[i]
                _, id_j = elist[j]
                pred = "与因果相关" if causal else "共现于"
                insert_rel(id_i, pred, id_j, filepath.name, causal)
                stats["relations_extracted"] += 1

    return stats


def process_all(dry_run=False):
    lib_dir = Path.home() / "xuzhi_genesis/centers/intelligence/seeds/library"
    results = []
    for f in sorted(lib_dir.glob("*.md")):
        print(f"  {f.name} ...", end=" ", flush=True)
        st = process_file(f, dry_run=dry_run)
        gc = st["sentences_garbage"]
        mk = st["sentences_meaningful"]
        en = st["entities_extracted"]
        print(f"✓ 总句{st['sentences_total']} 乱码{gc} 有效{mk} 实体{en}")
        results.append(st)
    return results


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--all", action="store_true")
    p.add_argument("--preview", action="store_true")
    p.add_argument("file", nargs="?")
    args = p.parse_args()

    if args.all:
        print("=== 处理全部 library 文件 ===")
        results = process_all(dry_run=args.preview)
        print(f"\n汇总: {len(results)}文件, "
              f"乱码{sum(r['sentences_garbage'] for r in results)}句, "
              f"有效{sum(r['sentences_meaningful'] for r in results)}句, "
              f"实体{sum(r['entities_extracted'] for r in results)}")
        if args.preview:
            for r in results[:3]:
                print(f"\n--- {r['file']} (编码:{r['encoding_detected']}) ---")
                for s in r["preview"][:3]:
                    print(f"  · {s[:80]}{'...' if len(s)>80 else ''}")

    elif args.file:
        fpath = Path(args.file)
        if not fpath.is_absolute():
            fpath = Path.home() / "xuzhi_genesis/centers/intelligence/seeds/library" / args.file
        import json; print(json.dumps(process_file(fpath, dry_run=args.preview), indent=2, ensure_ascii=False))

    else:
        p.print_help()
