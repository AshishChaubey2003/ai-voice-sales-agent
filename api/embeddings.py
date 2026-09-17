from functools import lru_cache

from fastembed import TextEmbedding

from api.config import get_settings


@lru_cache
def get_embedding_model() -> TextEmbedding:
    settings = get_settings()
    return TextEmbedding(
        model_name=settings.embedding_model,
        cache_dir=settings.embedding_cache_dir,
    )


def embed_passages(texts: list[str]) -> list[list[float]]:
    model = get_embedding_model()
    embed = getattr(model, "passage_embed", model.embed)
    return [vector.tolist() for vector in embed(texts)]


def embed_query(text: str) -> list[float]:
    model = get_embedding_model()
    embed = getattr(model, "query_embed", model.embed)
    return next(iter(embed([text]))).tolist()


def to_pgvector(values: list[float]) -> str:
    return "[" + ",".join(f"{value:.6f}" for value in values) + "]"