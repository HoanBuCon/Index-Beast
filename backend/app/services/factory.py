"""Select service once per app lifespan, loading no encoder in mock/llm_only modes.

Phụ trách: TV3 · [S3] Chat integration
"""

from app.rag.pipeline import ChatPipeline
from app.services.chat import ChatService, LiveChatService
from app.services.mock_chat import MockChatService


def build_chat_service(ctx) -> ChatService:
    settings = ctx.settings
    if settings.chat_mode == "mock":
        return MockChatService()
    retriever = None
    if settings.chat_mode == "rag":
        from app.rag.retriever import HybridRetriever
        from core.config import REPO_ROOT
        from core.encoders.onnx import FastEmbedEncoder
        from core.errors import UnavailableError
        from core.vector.store import QdrantStore

        if ctx.qdrant is None:
            raise UnavailableError("Kho tri thức RAG chưa được cấu hình.")
        retriever = HybridRetriever(
            FastEmbedEncoder(REPO_ROOT / "backend" / settings.rag_models_dir),
            QdrantStore(ctx.qdrant, settings.rag_collection),
            settings.rag_prefetch,
        )
    return LiveChatService(ChatPipeline(settings, ctx.llm, retriever))
