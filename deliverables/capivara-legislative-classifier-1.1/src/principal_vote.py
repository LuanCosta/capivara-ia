"""Seleção conservadora da votação principal por proposição.

Este módulo apenas produz candidatos para revisão. Ele não publica nem altera
dados do backend.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any


STAGE_PRIORITY = {
    "SECOND_ROUND": 40,
    "SINGLE_ROUND": 30,
    "FIRST_ROUND": 20,
    "UNKNOWN": 10,
    "OTHER_STAGE": 10,
}


def select_principal_votes(
    records: list[dict[str, Any]],
    classifications: list[dict[str, Any]],
) -> dict[str, Any]:
    """Propõe no máximo uma votação principal para cada proposição.

    Uma PEC com segundo turno explícito prefere esse turno. Empate, vínculo com
    várias proposições ou caso marcado para revisão produz INDETERMINATE.
    """

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record, output in zip(records, classifications, strict=True):
        classification = output["classification"]
        if classification["decisionRole"] != "MAIN_PROPOSAL_DECISION":
            continue
        references = record.get("proposalReferences") or []
        for reference in references:
            grouped[str(reference["id"])].append(
                {
                    "votingId": str(record["votingId"]),
                    "legislativeStage": classification["legislativeStage"],
                    "votingType": classification["votingType"],
                    "textForm": classification["textForm"],
                    "requiresHumanReview": classification["requiresHumanReview"],
                    "multipleProposalReferences": len(references) > 1,
                    "score": STAGE_PRIORITY.get(
                        classification["legislativeStage"], 0
                    ),
                }
            )

    proposal_ids = {
        str(reference["id"])
        for record in records
        for reference in record.get("proposalReferences") or []
    }
    selections = []
    for proposal_id in sorted(proposal_ids):
        candidates = sorted(
            grouped.get(proposal_id, []),
            key=lambda item: (-item["score"], item["votingId"]),
        )
        if not candidates:
            selections.append(
                _indeterminate(
                    proposal_id,
                    candidates,
                    "Nenhuma decisão principal foi sustentada pelo texto oficial.",
                )
            )
            continue

        best_score = candidates[0]["score"]
        best = [item for item in candidates if item["score"] == best_score]
        if len(best) != 1:
            selections.append(
                _indeterminate(
                    proposal_id,
                    candidates,
                    "Há empate entre candidatos com a mesma força de evidência.",
                )
            )
            continue

        winner = best[0]
        if winner["requiresHumanReview"] or winner["multipleProposalReferences"]:
            selections.append(
                _indeterminate(
                    proposal_id,
                    candidates,
                    "O melhor candidato ainda exige revisão humana ou possui múltiplos vínculos.",
                    suggested=winner["votingId"],
                )
            )
            continue

        selections.append(
            {
                "proposalId": proposal_id,
                "status": "SELECTED_FOR_HUMAN_VALIDATION",
                "selectedVotingId": winner["votingId"],
                "candidateVotingIds": [item["votingId"] for item in candidates],
                "rationale": (
                    "Maior estágio explicitamente comprovado entre decisões "
                    "principais; a seleção ainda não autoriza publicação."
                ),
            }
        )

    return {
        "warning": (
            "Proposta automática para validação humana; não conclui aprovação "
            "final, promulgação ou conversão em lei."
        ),
        "methodVersion": "principal-vote-rules-0.1.0",
        "selections": selections,
    }


def _indeterminate(
    proposal_id: str,
    candidates: list[dict[str, Any]],
    rationale: str,
    suggested: str | None = None,
) -> dict[str, Any]:
    return {
        "proposalId": proposal_id,
        "status": "INDETERMINATE",
        "selectedVotingId": None,
        "suggestedVotingId": suggested,
        "candidateVotingIds": [item["votingId"] for item in candidates],
        "rationale": rationale,
    }
