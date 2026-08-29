from typing import Annotated

from fastapi import Depends
from supabase import Client

from app.embeddings import EmbeddedChunk
from app.models import (
    CandidateSummary,
    ComparisonMaterial,
    DocumentAnalysisScores,
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

    def replace_chunks_and_analysis(
        self,
        document_id: int,
        chunks: list[EmbeddedChunk],
        scores: DocumentAnalysisScores,
        analysis_model: str,
        analysis_version: str,
    ) -> None:
        """Substitui chunks e análise temática na mesma transação do PostgreSQL."""

        new_chunks = [
            {
                "page": chunk.page,
                "content": chunk.content,
                "embedding": chunk.embedding,
            }
            for chunk in chunks
        ]
        self._client.rpc(
            "replace_proposal_chunks_with_analysis",
            {
                "target_document_id": document_id,
                "new_chunks": new_chunks,
                "new_analysis": scores.model_dump(),
                "analysis_model_name": analysis_model,
                "analysis_version_name": analysis_version,
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
        """Carrega o candidato e a análise do plano processado mais recente."""

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
            analysis_response = (
                self._client.table("proposal_document_analysis")
                .select(
                    "economy,health,education,security,social,infrastructure"
                )
                .eq("document_id", document_id)
                .maybe_single()
                .execute()
            )
            if analysis_response is not None and analysis_response.data:
                return ComparisonMaterial(
                    candidate=candidate,
                    scores=DocumentAnalysisScores.model_validate(
                        analysis_response.data
                    ),
                )

        return ComparisonMaterial(candidate=candidate, scores=None)


def get_document_repository(
    client: Annotated[Client, Depends(get_supabase_client)],
) -> ProposalDocumentRepository:
    """Monta o repository com o cliente fornecido pelo FastAPI."""

    return ProposalDocumentRepository(client)
