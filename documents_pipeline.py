#!/usr/bin/env python3
"""
documents_pipeline.py — 流式多格式文档 → 概念 → 知识图谱 pipeline
Xuzhi Genesis 情报中心智库升级核心模块
"""

import os, sys, re, json, sqlite3, hashlib
from pathlib import Path
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterator, Optional

# ─── Format Registry ──────────────────────────────────────────────────────────

FORMATTERS = {}

def register(fmt):
    def deco(cls):
        FORMATTERS[fmt] = cls()
        return cls
    return deco


# ─── Base Types ───────────────────────────────────────────────────────────────

@dataclass
class ExtractionResult:
    title: str
    author: str
    text: str          # full normalized text
    format: str
    source_path: str
    word_count: int
    encoding: str = 'utf-8'

@dataclass
class TextChunk:
    chunk_id: str
    text: str
    source_file: str
    chapter: Optional[str]
    offset_start: int  # char offset in full text
    offset_end: int

@dataclass
class ExtractedConcept:
    name: str
    type: str           # PERSON/WORK/THEORY/EVENT/GENERAL/LOCATION/ORGANIZATION
    source_chunk_id: str
    confidence: float
    aliases: list = None

    def to_entity(self):
        return {
            'name': self.name,
            'type': self.type,
            'source': 'concept_extractor',
            'confidence': self.confidence,
            'source_seed': self.source_chunk_id,
        }

@dataclass
class ExtractedRelation:
    subject: str
    predicate: str
    object: str
    source_chunk_id: str
    confidence: float


# ─── Extractors ──────────────────────────────────────────────────────────────

class BaseExtractor(ABC):
    def normalize(self, text: str) -> str:
        text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        return text.strip()

    @abstractmethod
    def extract(self, path: str) -> ExtractionResult:
        raise NotImplementedError


@register('txt')
class TXTExtractor(BaseExtractor):
    def extract(self, path: str) -> ExtractionResult:
        for enc in ('utf-8', 'gbk', 'gb2312', 'gb18030', 'latin-1'):
            try:
                with open(path, 'r', encoding=enc) as f:
                    raw = f.read()
                text = self.normalize(raw)
                return ExtractionResult(
                    title=Path(path).stem[:100],
                    author='Unknown', text=text,
                    format='txt', source_path=path,
                    word_count=len(text), encoding=enc
                )
            except UnicodeDecodeError:
                continue
        raise ValueError(f"Cannot decode {path}")


@register('md')
class MDExtractor(BaseExtractor):
    def extract(self, path: str) -> ExtractionResult:
        for enc in ('utf-8', 'gbk', 'gb2312', 'gb18030', 'latin-1'):
            try:
                with open(path, 'r', encoding=enc) as f:
                    raw = f.read()
                text = self.normalize(raw)
                return ExtractionResult(
                    title=Path(path).stem[:100],
                    author='Unknown', text=text,
                    format='md', source_path=path,
                    word_count=len(text), encoding=enc
                )
            except UnicodeDecodeError:
                continue
        raise ValueError(f"Cannot decode {path}")


@register('pdf')
class PDFExtractor(BaseExtractor):
    def extract(self, path: str) -> ExtractionResult:
        import fitz
        doc = fitz.open(path)
        parts = []
        for page in doc:
            t = page.get_text('text')
            if t.strip():
                parts.append(t)
        doc.close()
        text = self.normalize('\n\n'.join(parts))
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        title = lines[0][:100] if lines else Path(path).stem
        return ExtractionResult(
            title=title, author='Unknown', text=text,
            format='pdf', source_path=path,
            word_count=len(text)
        )

    def extract_pages_stream(self, path: str, page_limit: int = None):
        """Stream pages one by one without loading full text."""
        import fitz
        doc = fitz.open(path)
        total = len(doc)
        limit = page_limit or total
        for i in range(min(limit, total)):
            page = doc[i]
            text = page.get_text('text')
            if text.strip():
                yield i+1, self.normalize(text)
        doc.close()


@register('epub')
class EPUBExtractor(BaseExtractor):
    def extract(self, path: str) -> ExtractionResult:
        import zipfile
        from xml.etree import ElementTree as ET

        with zipfile.ZipFile(path, 'r') as z:
            opf_path = next((n for n in z.namelist() if n.endswith('.opf')), None)
            if not opf_path:
                raise ValueError(f"No OPF in {path}")

            opf_data = z.read(opf_path).decode('utf-8')
            opf_root = ET.fromstring(opf_data)
            opf_dir = os.path.dirname(opf_path)

            # Title / author
            title = Path(path).stem
            author = 'Unknown'
            for el in opf_root.iter():
                tag = el.tag.split('}')[-1]
                if tag == 'title' and el.text:
                    title = el.text.strip()[:100] or title
                if tag == 'creator' and el.text:
                    author = el.text.strip() or author

            # Spine
            manifest = {}
            for el in opf_root.iter():
                if 'id' in el.attrib and 'href' in el.attrib:
                    manifest[el.attrib['id']] = el.attrib['href']

            spine_ids = [
                el.attrib.get('idref')
                for el in opf_root.iter()
                if el.attrib.get('idref')
            ]

            text_parts = []
            for sid in spine_ids:
                href = manifest.get(sid)
                if not href:
                    continue
                item_path = os.path.join(opf_dir, href).replace('\\', '/')
                if item_path not in z.namelist():
                    continue
                # Stream: read in small chunks, decode immediately
                try:
                    raw = z.read(item_path)
                    try:
                        root = ET.fromstring(raw)
                        texts = []
                        for el in root.iter():
                            if el.text: texts.append(el.text)
                            if el.tail: texts.append(el.tail)
                        text_parts.append(' '.join(texts))
                    except ET.ParseError:
                        html_text = raw.decode('utf-8', errors='ignore')
                        clean = re.sub(r'<[^>]+>', ' ', html_text)
                        text_parts.append(clean)
                except Exception:
                    continue

        text = self.normalize(' '.join(text_parts))
        return ExtractionResult(
            title=title, author=author, text=text,
            format='epub', source_path=path,
            word_count=len(text)
        )


@register('docx')
class DOCXExtractor(BaseExtractor):
    def extract(self, path: str) -> ExtractionResult:
        import zipfile
        from xml.etree import ElementTree as ET

        with zipfile.ZipFile(path, 'r') as z:
            if 'word/document.xml' not in z.namelist():
                raise ValueError(f"No document.xml in {path}")

            raw = z.read('word/document.xml')
            root = ET.fromstring(raw)
            texts = []
            for el in root.iter():
                tag = el.tag.split('}')[-1]
                if tag == 't' and el.text:
                    texts.append(el.text)
                elif tag == 'p':
                    texts.append('\n')
                elif tag == 'tab':
                    texts.append('\t')

        text = self.normalize(''.join(texts))
        return ExtractionResult(
            title=Path(path).stem[:100],
            author='Unknown', text=text,
            format='docx', source_path=path,
            word_count=len(text)
        )


def extract_document(path: str) -> ExtractionResult:
    ext = Path(path).suffix.lower().lstrip('.')
    if ext not in FORMATTERS:
        raise ValueError(f"No extractor for .{ext}")
    return FORMATTERS[ext].extract(path)


# ─── Segmenter ───────────────────────────────────────────────────────────────

class TextSegmenter:
    """
    流式分块：
      1. 按章节拆分（多pattern检测）
      2. 每章节按句子流式切分（generator）
      3. 凑够 chunk_size 字后 yield 一个 TextChunk
    """

    def __init__(self, chunk_size: int = 1500):
        self.chunk_size = chunk_size

    def segment_stream(self, text: str, source: str) -> Iterator[TextChunk]:
        """Yields TextChunks without loading all into memory."""
        chapters = self._detect_chapters(text)
        offset = 0
        for ch_text, ch_title in chapters:
            yield from self._stream_chunks(ch_text, source, ch_title, offset)
            offset += len(ch_text) + 1

        if offset == 0:  # no chapters detected
            yield from self._stream_chunks(text, source, None, 0)

    def _detect_chapters(self, text: str) -> list[tuple[str, str]]:
        patterns = [
            (r'\n\s*(第[一二三四五六七八九十百零\d]+[章节篇部卷])[\s　]', 2),
            (r'\n\s*(\d+\.[\s　])', 2),
            (r'\n{2,}(#{1,6}\s*[^\n]+)\n', 3),
            (r'\n{2,}([^\n]{2,30})\n={3,}', 2),
        ]
        for pat, grp in patterns:
            matches = [(m.start(), m.group(grp).strip()[:50])
                       for m in re.finditer(pat, text)]
            if len(matches) >= 3:
                matches.sort()
                result = []
                for i, (start, title) in enumerate(matches):
                    end = matches[i+1][0] if i+1 < len(matches) else len(text)
                    ch_text = text[start:end]
                    if len(ch_text) > 500:
                        result.append((ch_text, title))
                if result:
                    return result
        return []

    def _stream_chunks(self, text: str, source: str,
                       chapter: Optional[str], offset_start: int) -> Iterator[TextChunk]:
        sentences = self._split_sentences(text)
        buf, buf_len, chunk_start = [], 0, offset_start

        for sent in sentences:
            slen = len(sent)
            if buf_len + slen > self.chunk_size and buf:
                chunk_text = ' '.join(buf)
                yield TextChunk(
                    chunk_id=hashlib.sha256(
                        f"{source}:{chunk_start}:{chunk_start+len(chunk_text)}".encode()
                    ).hexdigest()[:16],
                    text=chunk_text,
                    source_file=source,
                    chapter=chapter,
                    offset_start=chunk_start,
                    offset_end=chunk_start + len(chunk_text)
                )
                chunk_start += len(chunk_text) + 1
                buf, buf_len = [], 0
            buf.append(sent)
            buf_len += slen + 1

        if buf:
            chunk_text = ' '.join(buf)
            yield TextChunk(
                chunk_id=hashlib.sha256(
                    f"{source}:{chunk_start}:{chunk_start+len(chunk_text)}".encode()
                ).hexdigest()[:16],
                text=chunk_text,
                source_file=source,
                chapter=chapter,
                offset_start=chunk_start,
                offset_end=chunk_start + len(chunk_text)
            )

    def _split_sentences(self, text: str) -> list[str]:
        """Split into sentences, no loading of NLTK/spaCy required."""
        text = re.sub(r'[ \t]+', ' ', text)
        parts = re.split(r'(?<=[。！？!?\.;;])\s+', text)
        return [s.strip() for s in parts if len(s.strip()) > 8]


# ─── Concept Extractor ───────────────────────────────────────────────────────

class ConceptExtractor:
    def __init__(self):
        self._nlp = None
        self._load_nlp()

    def _load_nlp(self):
        try:
            import spacy
            for model in ['zh_core_web_sm', 'zh_core_web_md',
                          'en_core_web_sm', 'multilingual']:
                try:
                    self._nlp = spacy.load(model)
                    print(f"  [spaCy] model: {model}")
                    break
                except OSError:
                    continue
        except ImportError:
            print("  [spaCy] not installed")

    def extract_stream(self, chunk: TextChunk) -> tuple[list[ExtractedConcept], list[ExtractedRelation]]:
        concepts = []
        relations = []

        # NER via spaCy
        concepts.extend(self._ner(chunk))

        # Rule-based
        concepts.extend(self._rule_concepts(chunk))

        # Deduplicate
        seen = {}
        for c in concepts:
            k = c.name.lower()
            if k not in seen or c.confidence > seen[k].confidence:
                seen[k] = c
        concepts = list(seen.values())

        # Relations
        relations.extend(self._extract_relations(chunk, concepts))

        return concepts, relations

    def _ner(self, chunk: TextChunk) -> list[ExtractedConcept]:
        if self._nlp is None:
            return []
        concepts = []
        # Process max 50k chars at a time for safety
        doc = self._nlp(chunk.text[:50000])
        for ent in doc.ents:
            if 2 <= len(ent.text) <= 50:
                concepts.append(ExtractedConcept(
                    name=ent.text.strip(),
                    type=self._map_type(ent.label_),
                    source_chunk_id=chunk.chunk_id,
                    confidence=0.8
                ))
        return concepts

    def _map_type(self, label: str) -> str:
        return {
            'PERSON': 'PERSON', 'ORG': 'ORGANIZATION', 'GPE': 'LOCATION',
            'LOC': 'LOCATION', 'DATE': 'TIME', 'TIME': 'TIME',
            'EVENT': 'EVENT', 'WORK_OF_ART': 'WORK', 'LAW': 'LAW',
            'PRODUCT': 'WORK', 'PRODUCT': 'WORK',
        }.get(label, 'GENERAL')

    def _rule_concepts(self, chunk: TextChunk) -> list[ExtractedConcept]:
        text = chunk.text
        concepts = []

        # 《书名号》— works/titles
        for m in re.finditer(r'《([^《》]{2,30})》', text):
            concepts.append(ExtractedConcept(
                name=m.group(1), type='WORK',
                source_chunk_id=chunk.chunk_id, confidence=0.85
            ))

        # 「术语」— quoted terms
        for m in re.finditer(r'「([^「」]{2,20})」', text):
            concepts.append(ExtractedConcept(
                name=m.group(1), type='GENERAL',
                source_chunk_id=chunk.chunk_id, confidence=0.7
            ))

        # 【重点】— key terms
        for m in re.finditer(r'【([^【】]{2,20})】', text):
            concepts.append(ExtractedConcept(
                name=m.group(1), type='GENERAL',
                source_chunk_id=chunk.chunk_id, confidence=0.75
            ))

        # "Term" — quoted foreign terms
        for m in re.finditer(r'"([A-Za-z\u00c0-\u024f]{2,30})"', text):
            concepts.append(ExtractedConcept(
                name=m.group(1), type='GENERAL',
                source_chunk_id=chunk.chunk_id, confidence=0.7
            ))

        return concepts

    def _extract_relations(self, chunk: TextChunk,
                           concepts: list[ExtractedConcept]) -> list[ExtractedRelation]:
        relations = []
        text = chunk.text
        pred_map = [
            (r'([^\s，,。、；:：\n]{2,20})\s*(?:导致|造成|引起|使得)\s*([^\s，,。、；:：\n]{2,30})', 'causes'),
            (r'([^\s，,。、；:：\n]{2,20})\s*(?:属于|是.*之一部分)\s*([^\s，,。、；:：\n]{2,30})', 'related_to'),
            (r'([^\s，,。、；:：\n]{2,20})\s*(?:与|和)\s*([^\s，,。、；:：\n]{2,20})\s*(?:相关|有关|关联)', 'related_to'),
            (r'([^\s，,。、；:：\n]{2,20})\s*(?:认为|相信|指出|提出)\s*(.{3,50})', 'believes'),
        ]

        for pat, pred in pred_map:
            for m in re.finditer(pat, text):
                s, o = m.group(1).strip(), m.group(2).strip()[:30]
                if len(s) >= 2 and len(o) >= 2:
                    relations.append(ExtractedRelation(
                        subject=s, predicate=pred, object=o,
                        source_chunk_id=chunk.chunk_id, confidence=0.65
                    ))

        return relations


# ─── DB Writer ──────────────────────────────────────────────────────────────

def ensure_db(db_path: str):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    for table, cols in [
        ('entities', '''id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL,
            type TEXT, source TEXT, first_seen REAL, last_seen REAL,
            confidence REAL, source_seed TEXT'''),
        ('relations', '''id INTEGER PRIMARY KEY, subject_id INT, predicate TEXT,
            object_id INT, source TEXT, first_seen REAL, last_seen REAL,
            confidence REAL, source_seed TEXT, is_causal INT DEFAULT 0'''),
    ]:
        c.execute(f"CREATE TABLE IF NOT EXISTS {table} ({cols})")
    conn.commit()
    conn.close()


def write_batch(concepts: list[ExtractedConcept],
                relations: list[ExtractedRelation],
                db_path: str, source_file: str):
    import time
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    now = time.time()

    for concept in concepts:
        e = concept.to_entity()
        c.execute('''
            INSERT OR IGNORE INTO entities
            (name,type,source,first_seen,last_seen,confidence,source_seed)
            VALUES (?,?,?,?,?,?,?)
        ''', (e['name'], e['type'], e['source'], now, now,
              e['confidence'], e['source_seed']))
        c.execute('''
            UPDATE entities SET last_seen=?, confidence=?,
            type=COALESCE(type,'GENERAL') WHERE name=? AND source=?
        ''', (now, e['confidence'], e['name'], e['source']))

    # Build name→id map for this batch
    names = list({r.subject: None for r in relations}.keys()) + \
            list({r.object: None for r in relations}.keys())
    names = list(set(names))
    for name in names:
        c.execute('SELECT id FROM entities WHERE name=? LIMIT 1', (name,))
        row = c.fetchone()
        if row:
            if None in [None for n in names if n == name]:
                pass
            # simple update
            c.execute('INSERT OR IGNORE INTO entities (name,type,source,first_seen,last_seen,confidence,source_seed) VALUES (?,?,?,?,?,?,?)',
                      (name, 'GENERAL', 'concept_extractor', now, now, 0.5, 'relation_auto'))

    for rel in relations:
        c.execute('SELECT id FROM entities WHERE name=? LIMIT 1', (rel.subject,))
        s_row = c.fetchone()
        if not s_row:
            continue
        sub_id = s_row[0]

        c.execute('SELECT id FROM entities WHERE name=? LIMIT 1', (rel.object,))
        o_row = c.fetchone()
        if not o_row:
            c.execute('INSERT INTO entities (name,type,source,first_seen,last_seen,confidence,source_seed) VALUES (?,?,?,?,?,?,?)',
                      (rel.object, 'GENERAL', 'concept_extractor', now, now, 0.5, rel.source_chunk_id))
            c.execute('SELECT last_insert_rowid()')
            o_row = c.fetchone()

        if o_row:
            c.execute('''
                INSERT OR IGNORE INTO relations
                (subject_id,predicate,object_id,source,first_seen,last_seen,confidence,source_seed)
                VALUES (?,?,?,?,?,?,?,?)
            ''', (sub_id, rel.predicate, o_row[0], 'concept_extractor',
                  now, now, rel.confidence, rel.source_chunk_id))

    conn.commit()
    conn.close()


# ─── CLI Commands ─────────────────────────────────────────────────────────────

def cmd_scan(root: str):
    stats = {}
    files = []
    for dp, dn, fn in os.walk(root):
        for f in fn:
            ext = Path(f).suffix.lower().lstrip('.')
            if ext in FORMATTERS:
                stats[ext] = stats.get(ext, 0) + 1
                files.append(os.path.join(dp, f))
    print(f"\n{'Format':<10} {'Count':>6}")
    print('-' * 20)
    for k, v in sorted(stats.items()):
        print(f"  {k:<8} {v:>6}")
    print(f"  {'TOTAL':<8} {sum(stats.values()):>6}")
    for f in sorted(files)[:80]:
        print(f"  {f:<68} {os.path.getsize(f):>10,} B")
    if len(files) > 80:
        print(f"  ... +{len(files)-80} more")
    print()


def cmd_process(dir_or_file: str, db_path: str = None, sample_pages: int = None):
    segmenter = TextSegmenter(chunk_size=1500)
    concept_extractor = ConceptExtractor()

    files = []
    if os.path.isfile(dir_or_file):
        files = [dir_or_file]
    else:
        for dp, dn, fn in os.walk(dir_or_file):
            for f in fn:
                ext = Path(f).suffix.lower().lstrip('.')
                if ext in FORMATTERS:
                    files.append(os.path.join(dp, f))

    print(f"Files to process: {len(files)}\n")

    for fp in sorted(files):
        print(f"▶ {fp}")
        sz = os.path.getsize(fp)
        try:
            result = extract_document(fp)
            print(f"  [{result.format}] {result.word_count:,} chars | {result.title[:50]}")

            chunk_gen = segmenter.segment_stream(result.text, fp)

            all_concepts, all_relations = [], []
            chunk_count = 0

            for chunk in chunk_gen:
                concepts, relations = concept_extractor.extract_stream(chunk)
                all_concepts.extend(concepts)
                all_relations.extend(relations)
                chunk_count += 1
                if chunk_count <= 3:
                    sample = concepts[:5]
                    print(f"  chunk[{chunk_count}]: {len(concepts)} concepts | "
                          f"{[c.name for c in sample if c.type in ('PERSON','WORK','THEORY')]}")

            seen = {}
            for c in all_concepts:
                k = c.name.lower()
                if k not in seen or c.confidence > seen[k].confidence:
                    seen[k] = c
            unique = list(seen.values())

            print(f"  ✓ {chunk_count} chunks | {len(unique)} unique concepts | "
                  f"{len(all_relations)} relations\n")

            if db_path:
                write_batch(unique, all_relations, db_path, fp)
                print(f"  → {db_path}")

        except Exception as e:
            print(f"  ✗ ERROR: {e}\n")

    if not db_path:
        print("(no --db, results not persisted)")


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == 'scan' and len(sys.argv) >= 3:
        cmd_scan(sys.argv[2])
    elif cmd == 'process' and len(sys.argv) >= 3:
        db = sys.argv[3] if len(sys.argv) >= 4 else None
        cmd_process(sys.argv[2], db)
    else:
        print(f"Usage: {sys.argv[0]} scan|process <path> [db_path]")
