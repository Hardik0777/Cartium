"""The assistant's search index: products, FAQs and policies embedded in ChromaDB.

Only ids and searchable text live in the index. Prices, stock and whether a product is still for
sale are looked up live in the database for every answer, so the assistant never quotes an old
price or recommends a product that was removed after the index was built."""
import logging
import re
from typing import Protocol

from sqlalchemy.orm import Session

from app.core.config import settings
from app.data.knowledge import FAQS, POLICIES
from app.services.catalog import visible_products

log = logging.getLogger(__name__)
COLLECTION = "cartium_knowledge"
STOPWORDS = {"the", "and", "for", "with", "you", "your", "have", "any", "can", "how", "what", "does", "need",
             "want", "show", "some", "are", "is", "my", "me", "to", "of", "in", "a", "an", "do", "i", "it", "much"}
NAME_BOOST = 0.5  # hybrid search: exact words in a title count on top of meaning-based similarity


class Embedder(Protocol):
    def __call__(self, input: list[str]) -> list[list[float]]: ...


_embedder: Embedder | None = None
_client = None


def set_embedder(embedder: Embedder | None) -> None:
    """Tests swap in a tiny offline embedder. In the app, ChromaDB's default (all-MiniLM-L6-v2) is used."""
    global _embedder, _client
    _embedder, _client = embedder, None


def _collection():
    global _client
    import chromadb
    from chromadb.utils import embedding_functions

    if _client is None:
        _client = chromadb.PersistentClient(path=settings.ai_index_dir)
    fn = _embedder or embedding_functions.DefaultEmbeddingFunction()  # sentence-transformers MiniLM via ONNX
    return _client.get_or_create_collection(COLLECTION, embedding_function=fn, metadata={"hnsw:space": "cosine"})


def product_text(p) -> str:
    return f"{p.name}. Brand: {p.brand}. Category: {p.category.name}. {p.description}"


def rebuild(db: Session) -> dict:
    """Re-indexes everything. Run by the seed script, by admins, and automatically if the index is empty."""
    col = _collection()
    existing = col.get(include=[])["ids"]
    if existing:
        col.delete(ids=existing)
    ids, docs, metas = [], [], []
    products = db.scalars(visible_products()).unique().all()
    for p in products:
        ids.append(f"product:{p.id}")
        docs.append(product_text(p))
        metas.append({"kind": "product", "ref": p.id, "title": p.name})
    for i, (q, a) in enumerate(FAQS):
        ids.append(f"faq:{i}")
        docs.append(f"{q} {a}")
        metas.append({"kind": "faq", "ref": i, "title": q})
    for i, (title, text) in enumerate(POLICIES):
        ids.append(f"policy:{i}")
        docs.append(f"{title} policy. {text}")
        metas.append({"kind": "policy", "ref": i, "title": title})
    for start in range(0, len(ids), 200):
        col.add(ids=ids[start:start + 200], documents=docs[start:start + 200], metadatas=metas[start:start + 200])
    log.info("Assistant index rebuilt: %d products, %d FAQs, %d policies", len(products), len(FAQS), len(POLICIES))
    return {"products": len(products), "faqs": len(FAQS), "policies": len(POLICIES)}


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2 and w not in STOPWORDS}


def search(db: Session, query: str, k: int = 8) -> list[dict]:
    """Hybrid search: meaning-based similarity from the embeddings, plus a boost when the words the
    shopper typed appear in a product's name or an FAQ's question. Embeddings are good at "something
    for making chai" but can rank an exact name like "mechanical keyboard" below loosely related items."""
    col = _collection()
    if col.count() == 0:
        rebuild(db)
    res = col.query(query_texts=[query], n_results=min(max(k * 3, 20), col.count()))  # wider net, then re-rank
    wanted = _words(query)
    hits = []
    for meta, doc, dist in zip(res["metadatas"][0], res["documents"][0], res["distances"][0]):
        overlap = len(wanted & _words(meta["title"])) / len(wanted) if wanted else 0
        hits.append({**meta, "text": doc, "semantic": round(1 - dist, 3),
                     "score": round(1 - dist + NAME_BOOST * overlap, 3)})
    hits.sort(key=lambda h: h["score"], reverse=True)
    return hits[:k]


def health() -> dict:
    try:
        return {"index": "ok", "documents": _collection().count()}
    except Exception as exc:  # e.g. the embedding model couldn't be downloaded
        return {"index": "unavailable", "error": type(exc).__name__}
