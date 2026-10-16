"""Audita o corpus congelado e executa o protótipo sem rede ou banco."""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
from typing import Any

from classifier import classify_record
from principal_vote import select_principal_votes


PRIORITY_REVIEW_IDS = {
    "2610975-23",
    "2618177-73",
    "2624161-25",
    "2624161-43",
    "2624161-46",
    "2624161-49",
}


def audit(data: dict[str, Any]) -> dict[str, Any]:
    records = data["records"]
    keys = [(item["house"], item["votingId"]) for item in records]
    proposal_metadata = data["proposalMetadataById"]
    broken_references = []
    relation_mismatches = []
    raw_mismatches = []

    for record in records:
        references = {str(item["id"]) for item in record["proposalReferences"]}
        affected = {str(item["id"]) for item in record["affectedProposals"]}
        raw_affected = {
            str(item["id"])
            for item in record["rawMetadata"]["officialVotingResponse"]["dados"]
            .get("proposicoesAfetadas", [])
        }
        broken_references.extend(
            {
                "votingId": record["votingId"],
                "proposalId": proposal_id,
            }
            for proposal_id in references
            if proposal_id not in proposal_metadata
        )
        if references != affected:
            relation_mismatches.append(record["votingId"])
        if affected != raw_affected:
            raw_mismatches.append(record["votingId"])

    classifications = [classify_record(record) for record in records]
    return {
        "corpus": {
            "records": len(records),
            "uniqueHouseVotingIds": len(set(keys)),
            "duplicateHouseVotingIds": len(keys) - len(set(keys)),
            "houses": dict(collections.Counter(item["house"] for item in records)),
            "minDate": min(item["date"] for item in records),
            "maxDate": max(item["date"] for item in records),
            "proposalMetadataCount": len(proposal_metadata),
            "proposalReferenceCount": sum(
                len(item["proposalReferences"]) for item in records
            ),
            "recordsWithMultipleProposalReferences": sum(
                len(item["proposalReferences"]) > 1 for item in records
            ),
        },
        "integrity": {
            "brokenProposalReferences": broken_references,
            "proposalReferenceVsAffectedMismatches": relation_mismatches,
            "affectedVsRawMismatches": raw_mismatches,
        },
        "availability": {
            "originalApprovalIndicator": dict(
                collections.Counter(
                    str(item["result"]["originalApprovalIndicator"])
                    for item in records
                )
            ),
            "possibleObjectsEmpty": sum(not item["possibleObjects"] for item in records),
            "registeredEffectsEmpty": sum(
                not item["registeredEffects"] for item in records
            ),
            "latestVotingOpeningDescriptionNull": sum(
                item["latestVotingOpening"]["description"] is None
                for item in records
            ),
            "eventIdNull": sum(item["event"]["id"] is None for item in records),
        },
        "prototype": {
            "votingTypeCounts": dict(
                collections.Counter(
                    item["classification"]["votingType"]
                    for item in classifications
                )
            ),
            "textDecisionStatusCounts": dict(
                collections.Counter(
                    item["classification"]["textDecisionStatus"]
                    for item in classifications
                )
            ),
            "decisionRoleCounts": dict(
                collections.Counter(
                    item["classification"]["decisionRole"]
                    for item in classifications
                )
            ),
            "methodCounts": dict(
                collections.Counter(item["method"] for item in classifications)
            ),
            "requiresHumanReview": sum(
                item["classification"]["requiresHumanReview"]
                for item in classifications
            ),
            "importantCaveat": (
                "Counts are prototype outputs, not accuracy metrics or human labels."
            ),
        },
    }


def build_review_queue(data: dict[str, Any], target_size: int = 100) -> dict[str, Any]:
    """Seleciona casos diversos; não os transforma em padrão-ouro."""

    records = data["records"]
    parent: dict[str, str] = {}

    def find(value: str) -> str:
        parent.setdefault(value, value)
        if parent[value] != value:
            parent[value] = find(parent[value])
        return parent[value]

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    for record in records:
        ids = [str(item["id"]) for item in record["proposalReferences"]]
        for proposal_id in ids:
            find(proposal_id)
        for proposal_id in ids[1:]:
            union(ids[0], proposal_id)

    candidates = []
    for record in records:
        output = classify_record(record)
        ids = [str(item["id"]) for item in record["proposalReferences"]]
        group_key = find(ids[0]) if ids else f"voting:{record['votingId']}"
        candidates.append((record, output, group_key))

    pools = {}
    for voting_type in sorted({item[1]["classification"]["votingType"] for item in candidates}):
        pool = [
            item
            for item in candidates
            if item[1]["classification"]["votingType"] == voting_type
        ]
        pool.sort(
            key=lambda item: (
                not item[1]["classification"]["requiresHumanReview"],
                -len(item[0]["proposalReferences"]),
                item[0]["votingId"],
            )
        )
        pools[voting_type] = pool

    selected_items = [
        item for item in candidates if item[0]["votingId"] in PRIORITY_REVIEW_IDS
    ]
    selected_ids = {item[0]["votingId"] for item in selected_items}
    for voting_type in pools:
        pools[voting_type] = [
            item
            for item in pools[voting_type]
            if item[0]["votingId"] not in selected_ids
        ]
    while len(selected_items) < min(target_size, len(candidates)):
        added = False
        for voting_type in sorted(pools):
            if pools[voting_type]:
                selected_items.append(pools[voting_type].pop(0))
                added = True
                if len(selected_items) == target_size:
                    break
        if not added:
            break

    selected = []
    for record, output, group_key in selected_items:
        selected.append(
            {
                "house": record["house"],
                "votingId": record["votingId"],
                "groupKey": group_key,
                "officialDescription": record["description"],
                "openingDescription": record["latestVotingOpening"]["description"],
                "proposalReferences": output["proposalReferences"],
                "automaticProposal": output["classification"],
                "method": output["method"],
                "ruleId": output["ruleId"],
                "evidence": output["evidence"],
                "annotationStatus": "AWAITING_HUMAN_REVIEW",
                "humanLabel": None,
                "ambiguityNotes": output["notes"],
            }
        )
    return {
        "warning": "Review queue only; no item is human-validated ground truth.",
        "grouping": "Connected components of proposal references.",
        "selectionMethod": (
            "Round-robin by proposed votingType, prioritizing review flags and "
            "multiple proposal references."
        ),
        "records": selected,
    }


def render_review_table(queue: dict[str, Any]) -> str:
    """Produz uma tabela legível; o JSON continua sendo a fonte completa."""

    lines = [
        "# Tabela para validação humana",
        "",
        "> Nenhum rótulo desta tabela foi validado por humano. `humanLabel` está nulo no JSON correspondente.",
        "",
        "| # | votingId | Grupo | Tipo sugerido | Papel da decisão | Forma do texto | Mecanismo | Revisão | Evidência oficial |",
        "|---:|---|---|---|---|---|---|---|---|",
    ]
    for index, item in enumerate(queue["records"], start=1):
        proposal = item["automaticProposal"]
        evidence = item["evidence"][0]["officialExcerpt"] if item["evidence"] else item["officialDescription"]
        evidence = _markdown_cell(evidence)
        lines.append(
            "| {index} | `{voting_id}` | `{group}` | `{kind}` | `{role}` | `{form}` | `{mechanism}` | {review} | {evidence} |".format(
                index=index,
                voting_id=item["votingId"],
                group=item["groupKey"],
                kind=proposal["votingType"],
                role=proposal["decisionRole"],
                form=proposal["textForm"],
                mechanism=proposal["contextualMechanism"] or "—",
                review="sim" if proposal["requiresHumanReview"] else "amostra de controle",
                evidence=evidence,
            )
        )
    lines.extend(
        [
            "",
            "A evidência integral, URLs, abertura, vínculos e campos para anotação estão em `human_review_queue.json`.",
            "",
        ]
    )
    return "\n".join(lines)


def _markdown_cell(value: str) -> str:
    return " ".join(value.split()).replace("|", "\\|").replace("\n", " ")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--classifications", type=Path)
    parser.add_argument("--review-queue", type=Path)
    parser.add_argument("--review-table", type=Path)
    parser.add_argument("--principal-votes", type=Path)
    args = parser.parse_args()

    data = json.loads(args.corpus.read_text(encoding="utf-8"))
    summary = audit(data)
    rendered = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.summary:
        args.summary.parent.mkdir(parents=True, exist_ok=True)
        args.summary.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)

    classifications = [classify_record(item) for item in data["records"]]
    if args.classifications:
        output = {
            "warning": "Automatic proposals; not human-validated ground truth.",
            "records": classifications,
        }
        args.classifications.parent.mkdir(parents=True, exist_ok=True)
        args.classifications.write_text(
            json.dumps(output, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    review_queue = build_review_queue(data)
    if args.review_queue:
        args.review_queue.parent.mkdir(parents=True, exist_ok=True)
        args.review_queue.write_text(
            json.dumps(review_queue, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    if args.review_table:
        args.review_table.parent.mkdir(parents=True, exist_ok=True)
        args.review_table.write_text(
            render_review_table(review_queue),
            encoding="utf-8",
        )
    if args.principal_votes:
        args.principal_votes.parent.mkdir(parents=True, exist_ok=True)
        args.principal_votes.write_text(
            json.dumps(
                select_principal_votes(data["records"], classifications),
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    main()
