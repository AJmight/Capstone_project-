"""
RAG step 1-3: ingestion, chunking and a BM25 search index (Week 3).
===================================================================

WHAT "RAG" MEANS HERE
---------------------
Retrieval-Augmented Generation: before the model answers a policy question, we
SEARCH our own trusted documents (knowledge/corpus/*.md) and give the model only
the most relevant passages, labelled [S1], [S2], ... The model must answer from
those passages and cite them. If nothing relevant is found, the system says the
information is not in our documents instead of letting the model guess.

THE PIPELINE IN THIS FILE
-------------------------
  1. INGEST   read every .md file in knowledge/corpus/
  2. CHUNK    split each document at its "## " section headings; a long section is
              split again into windows of about 120 words with 30 words of overlap
              (overlap = a sentence cut at a boundary still appears whole in one chunk)
  3. INDEX    tokenise each chunk and build BM25 statistics
  4. SEARCH   score every chunk against the question; return the best ones above
              a minimum score (MIN_SCORE), else nothing

WHY BM25 (keyword search) AND NOT EMBEDDINGS
--------------------------------------------
BM25 is a standard ranking formula used by search engines (Huyen, AI Engineering,
Ch. 6 "term-based retrieval"). For a small corpus of ~40 chunks it is accurate
enough, needs no extra library or API quota, gives the same result every run, and
a reviewer can see exactly why a chunk scored high. Its known weakness is
synonyms ("sign off" vs "approve") - see the Week 3 failure catalogue. Embedding
search is listed as future work.

BM25 IN ONE PARAGRAPH
---------------------
For each word in the question that also appears in a chunk, add:
    idf(word) * tf * (k1 + 1) / (tf + k1 * (1 - b + b * chunk_length / average_length))
idf is high for rare words ("prepayment") and low for common ones ("shop");
tf is how often the word appears in the chunk; the length part stops long chunks
winning just because they contain more words. k1 = 1.5, b = 0.75 are the usual values.

Owner: Mwesigwa Arnold Mugahi (AI Engineering Lead)
Version: 1.1.0 (Week 3: stemmer fix, boilerplate chunks removed)
"""

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------
import math                                   # log() for idf
import re                                     # tokenising and heading detection
from collections import Counter               # word counts per chunk
from dataclasses import dataclass             # Chunk record
from functools import lru_cache               # build the index once per process
from pathlib import Path

# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
INDEX_VERSION = "1.1.0"      # bump when chunking/tokenising changes (results are saved per version)
CORPUS_DIR = Path("knowledge/corpus")
WINDOW_WORDS = 120          # max words per chunk before a section is split again
OVERLAP_WORDS = 30          # words repeated between neighbouring windows
K1, B = 1.5, 0.75           # standard BM25 parameters
MIN_SCORE = 2.0             # below this the best chunk is treated as "not relevant" (tuned in Week 3 tests)
HEADING_BOOST = 2           # heading words are counted this many times (a heading names the topic)

# Very common words that carry no meaning for search.
STOPWORDS = set("""a an and are as at be been but by can do does for from has have how i if in into is it
its may me must my no not of on or our should so than that the their them then there these they this
to us was we what when where which who whom why will with you your would could shall any all also only
up out about more most per own one two""".split())


@dataclass
class Chunk:
    chunk_id: str      # e.g. "POL-01#approval-thresholds" or "...#approval-thresholds-2"
    doc_id: str        # e.g. "POL-01"
    title: str         # document title (first "# " line)
    section: str       # section heading
    text: str          # the passage itself
    source: str        # file path, for the source register / citations


# ---------------------------------------------------------------------------
# Tokenising
# ---------------------------------------------------------------------------
def tokenize(text: str) -> list[str]:
    """
    Lower-case words with stopwords removed and a light suffix strip, so
    "approvals", "approved" and "approve" all become "approv".
    Numbers keep their digits: "UGX 500,000" -> ["ugx", "500000"].
    """
    text = re.sub(r"(?<=\d),(?=\d)", "", text.lower())          # 500,000 -> 500000
    words = re.findall(r"[a-z0-9]+", text)
    out = []
    for w in words:
        if w in STOPWORDS:
            continue
        # Tiny stemmer. v1.1.0 added "ies" and "y" so delivery / deliveries / deliver all become
        # "deliver" (v1.0.0 missed "how many days to deliver" -> "Delivery" section: failure R-1).
        for suffix in ("ies", "ing", "ed", "es", "s", "al", "y"):
            if len(w) > 4 and w.endswith(suffix):
                w = w[: -len(suffix)]
                break
        out.append(w)
    return out


# ---------------------------------------------------------------------------
# Ingest + chunk
# ---------------------------------------------------------------------------
def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def load_chunks(corpus_dir: Path | None = None) -> list[Chunk]:
    """Read every document and split it into section chunks (and windows for long sections)."""
    corpus_dir = corpus_dir or CORPUS_DIR
    chunks: list[Chunk] = []
    for path in sorted(corpus_dir.glob("*.md")):
        doc_id = path.stem.split("_")[0]                       # "POL-01_procurement-policy" -> "POL-01"
        lines = path.read_text(encoding="utf-8").splitlines()
        title = next((l[2:].strip() for l in lines if l.startswith("# ")), path.stem)
        sections, current, body = [], "Introduction", []
        for line in lines:
            if line.startswith("## "):                          # a new section starts
                if " ".join(body).strip():
                    sections.append((current, " ".join(body).strip()))
                current, body = line[3:].strip(), []
            elif not line.startswith("# "):
                body.append(line.strip())
        if " ".join(body).strip():
            sections.append((current, " ".join(body).strip()))

        for section, text in sections:
            # v1.1.0: skip the one-line "Synthetic, team-created document..." note at the top of each
            # file. It became an "Introduction" chunk that matched unrelated questions through words
            # like "Kampala" (failure R-3). Provenance is kept in knowledge/source-register.md instead.
            if section == "Introduction" and text.lower().startswith("synthetic"):
                continue
            words = text.split()
            step = WINDOW_WORDS - OVERLAP_WORDS
            starts = range(0, max(len(words) - OVERLAP_WORDS, 1), step) if len(words) > WINDOW_WORDS else [0]
            for n, start in enumerate(starts, 1):
                piece = " ".join(words[start:start + WINDOW_WORDS])
                suffix = f"-{n}" if len(starts) > 1 else ""
                chunks.append(Chunk(chunk_id=f"{doc_id}#{_slug(section)}{suffix}", doc_id=doc_id,
                                    title=title, section=section, text=piece, source=path.as_posix()))
    return chunks


# ---------------------------------------------------------------------------
# BM25 index
# ---------------------------------------------------------------------------
class BM25Index:
    """Holds the chunks and the statistics BM25 needs; search() ranks chunks for a query."""

    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        # Each chunk's searchable words: heading words (boosted) + title words + text words.
        self.doc_tokens = [tokenize(f"{c.section} " * HEADING_BOOST + f"{c.title} {c.text}") for c in chunks]
        self.tf = [Counter(toks) for toks in self.doc_tokens]
        self.lengths = [len(toks) for toks in self.doc_tokens]
        self.avg_len = sum(self.lengths) / max(len(self.lengths), 1)
        df = Counter(word for toks in self.doc_tokens for word in set(toks))     # chunks containing each word
        n = len(chunks)
        # BM25 idf with +1 inside the log so very common words never go negative.
        self.idf = {w: math.log(1 + (n - d + 0.5) / (d + 0.5)) for w, d in df.items()}

    def score(self, query_tokens: list[str], i: int) -> float:
        tf, length, s = self.tf[i], self.lengths[i], 0.0
        for w in query_tokens:
            if w in tf:
                f = tf[w]
                s += self.idf[w] * f * (K1 + 1) / (f + K1 * (1 - B + B * length / self.avg_len))
        return s

    def search(self, query: str, top_k: int = 3, min_score: float = MIN_SCORE) -> list[dict]:
        """Best chunks for the query, highest score first, only those scoring >= min_score."""
        q = tokenize(query)
        scored = sorted(((self.score(q, i), i) for i in range(len(self.chunks))), reverse=True)
        out = []
        for s, i in scored[:top_k]:
            if s < min_score:
                break
            c = self.chunks[i]
            out.append({"chunk_id": c.chunk_id, "doc_id": c.doc_id, "title": c.title,
                        "section": c.section, "score": round(s, 2), "text": c.text, "source": c.source})
        return out


@lru_cache(maxsize=1)
def get_index() -> BM25Index:
    """Build the index once per run (about 40 chunks: milliseconds)."""
    return BM25Index(load_chunks())
