from typing import Annotated

from fastapi import Depends
from supabase import Client

from app.embeddings import EmbeddedChunk
from app.models import (
    CandidateSummary,
    ComparisonMaterial,
    ProcessedChunk,
    ProposalDocument,
    RetrievedChunk,
)
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

    def get_comparison_material(
        self,
        candidate_id: int,
    ) -> ComparisonMaterial | None:
        """Carrega o candidato e o plano mais recente que possua chunks."""

        candidate_response = (
            self._client.table("candidates")
            .select("id,nome,partido,numero,imagem")
            .eq("id", candidate_id)
            .maybe_single()
            .execute()
        )
        if candidate_response is None or candidate_response.data is None:
            return None

        candidate_data = candidate_response.data
        candidate = CandidateSummary(
            id=candidate_data["id"],
            name=candidate_data["nome"],
            party=candidate_data["partido"],
            number=candidate_data["numero"],
            image=candidate_data["imagem"],
        )

        documents_response = (
            self._client.table("proposal_documents")
            .select("id,election_year")
            .eq("candidate_id", candidate_id)
            .order("election_year", desc=True)
            .execute()
        )
        documents = (
            documents_response.data
            if documents_response is not None and documents_response.data
            else []
        )

        for document in documents:
            document_id = int(document["id"])
            chunks_response = (
                self._client.table("proposal_chunks")
                .select("id,document_id,content,embedding")
                .eq("document_id", document_id)
                .order("id")
                .execute()
            )
            if chunks_response is not None and chunks_response.data:
                return ComparisonMaterial(
                    candidate=candidate,
                    chunks=[
                        ProcessedChunk.model_validate(chunk)
                        for chunk in chunks_response.data
                    ],
                )

        return ComparisonMaterial(candidate=candidate, chunks=[])


def get_document_repository(
    client: Annotated[Client, Depends(get_supabase_client)],
) -> ProposalDocumentRepository:
    """Monta o repository com o cliente fornecido pelo FastAPI."""

    return ProposalDocumentRepository(client)
