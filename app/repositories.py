from typing import Annotated

from fastapi import Depends
from supabase import Client

from app.embeddings import EmbeddedChunk
from app.models import ProposalDocument, RetrievedChunk
from app.supabase_client import get_supabase_client


class ProposalDocumentRepository:
    """Executa as consultas da tabela proposal_documents."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def get_by_id(self, document_id: int) -> ProposalDocument | None:
        response = (
            self._client.table("proposal_documents")
            .select(
                "id,candidate_id,title,document_url,source_url,"
                "election_year,created_at"
            )
            .eq("id", document_id)
            .maybe_single()
            .execute()
        )

        if response is None or response.data is None:
            return None

        return ProposalDocument.model_validate(response.data)

    def replace_chunks(
        self,
        document_id: int,
        chunks: list[EmbeddedChunk],
    ) -> None:
        """Substitui todos os chunks do documento em uma transação no banco."""

        new_chunks = [
            {
                "page": chunk.page,
                "content": chunk.content,
                "embedding": chunk.embedding,
            }
            for chunk in chunks
        ]
        self._client.rpc(
            "replace_proposal_chunks",
            {
                "target_document_id": document_id,
                "new_chunks": new_chunks,
            },
        ).execute()

    def match_chunks(
        self,
        candidate_id: int,
        query_embedding: list[float],
        match_count: int = 5,
    ) -> list[RetrievedChunk]:
        """Busca chunks semelhantes, limitados aos documentos do candidato."""

        response = self._client.rpc(
            "match_proposal_chunks",
            {
                "query_embedding": query_embedding,
                "requested_candidate_id": candidate_id,
                "match_count": match_count,
            },
        ).execute()

        if response is None or response.data is None:
            return []

        return [RetrievedChunk.model_validate(item) for item in response.data]


def get_document_repository(
    client: Annotated[Client, Depends(get_supabase_client)],
) -> ProposalDocumentRepository:
    """Monta o repository com o cliente fornecido pelo FastAPI."""

    return ProposalDocumentRepository(client)
