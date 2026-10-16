"""Protótipo offline e conservador para classificar votações legislativas.

Este módulo não é importado pela aplicação FastAPI. Ele produz sugestões
auditáveis e abstém-se quando o texto oficial não sustenta uma conclusão.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any


SCHEMA_VERSION = "1.1"
CLASSIFIER_VERSION = "rules-0.3.0"

VOTING_TYPES = {
    "REQUIREMENT",
    "URGENCY_REQUEST",
    "AMENDMENT",
    "HIGHLIGHT",
    "SUBSTITUTE_TEXT",
    "BASE_TEXT",
    "FINAL_WORDING",
    "OTHER_PROCEDURAL",
    "OTHER_SUBSTANTIVE",
    "UNKNOWN",
}


def classify_record(record: dict[str, Any]) -> dict[str, Any]:
    """Classifica um registro sem usar histórico como prova causal."""

    description = _clean(record.get("description"))
    opening = _clean((record.get("latestVotingOpening") or {}).get("description"))
    voting_type, rule_id, source, excerpt = _classify_voting_type(
        description,
        opening,
    )
    stage, stage_evidence = _classify_stage(description, opening)
    result, result_evidence = _classify_result(description)
    text_status = _text_decision_status(voting_type, source)
    text_form = _classify_text_form(voting_type, description, opening)
    contextual_mechanism = _contextual_mechanism(voting_type, opening)
    decision_role = _classify_decision_role(
        voting_type,
        text_form,
        description,
        opening,
    )
    object_status = (
        "CONFIRMED_FROM_EXPLICIT_OFFICIAL_TEXT"
        if voting_type != "UNKNOWN" and source == "description"
        else "POSSIBLE_FROM_CONTEXT"
        if voting_type != "UNKNOWN"
        else "UNKNOWN"
    )

    evidence = []
    if excerpt:
        evidence.append(
            {
                "sourceField": (
                    "description"
                    if source == "description"
                    else "latestVotingOpening.description"
                ),
                "officialExcerpt": excerpt,
                "officialReference": _voting_reference(record),
                "supports": ["votingType", "objectStatus"],
            }
        )
    if stage_evidence:
        evidence.append(
            {
                "sourceField": stage_evidence[0],
                "officialExcerpt": stage_evidence[1],
                "officialReference": _voting_reference(record),
                "supports": ["legislativeStage"],
            }
        )
    if result_evidence:
        evidence.append(
            {
                "sourceField": "description",
                "officialExcerpt": result_evidence,
                "officialReference": _voting_reference(record),
                "supports": ["deliberationResult"],
            }
        )
    if decision_role == "MAIN_PROPOSAL_DECISION" and description:
        evidence.append(
            {
                "sourceField": "description",
                "officialExcerpt": description,
                "officialReference": _voting_reference(record),
                "supports": ["decisionRole"],
            }
        )

    ambiguous_generic = _is_generic_description(description)
    joint_amendment_vote = _is_joint_amendment_vote(description)
    requires_review = (
        voting_type == "UNKNOWN"
        or source != "description"
        or ambiguous_generic
        or object_status != "CONFIRMED_FROM_EXPLICIT_OFFICIAL_TEXT"
        or contextual_mechanism is not None
        or joint_amendment_vote
        or decision_role == "INDETERMINATE"
    )

    return {
        "schemaVersion": SCHEMA_VERSION,
        "house": str(record.get("house") or "UNKNOWN"),
        "votingId": str(record.get("votingId") or ""),
        "input": {
            "officialDataHash": official_data_hash(record),
            "sourceExtractedAt": _source_fetched_at(record),
        },
        "classification": {
            "votingType": voting_type,
            "legislativeStage": stage,
            "deliberationResult": result,
            "textDecisionStatus": text_status,
            "textForm": text_form,
            "decisionRole": decision_role,
            "contextualMechanism": contextual_mechanism,
            "objectStatus": object_status,
            "houseCompletionStatus": "INDETERMINATE",
            "individualVoteAvailability": _individual_vote_availability(record),
            "requiresHumanReview": requires_review,
        },
        "provenObject": (
            {
                "kind": voting_type,
                "officialText": excerpt,
                "proposalId": None,
                "note": (
                    "O texto comprova o tipo do objeto, mas não autoriza copiar "
                    "automaticamente um proposalReference como seu ID."
                ),
            }
            if object_status == "CONFIRMED_FROM_EXPLICIT_OFFICIAL_TEXT"
            else None
        ),
        "result": {
            "originalApprovalIndicator": (record.get("result") or {}).get(
                "originalApprovalIndicator"
            ),
            "officialDescription": description,
        },
        "proposalReferences": [
            {
                "id": str(item.get("id")),
                "identification": item.get("identification"),
                "relation": item.get("relation"),
            }
            for item in record.get("proposalReferences", [])
        ],
        "evidence": evidence,
        "method": "RULE_HIGH_PRECISION" if rule_id else "UNCLASSIFIED",
        "ruleId": rule_id,
        "modelVersion": None,
        "classifierVersion": CLASSIFIER_VERSION,
        "classifiedAt": datetime.now(timezone.utc).isoformat(),
        "annotationStatus": "AUTOMATIC_PROPOSAL_NOT_HUMAN_VALIDATED",
        "publication": {
            "eligibility": "BLOCKED_PENDING_REVIEW",
            "reasons": [
                "Protótipo automático sem validação humana.",
                *(
                    ["Objeto ou contexto exige revisão específica."]
                    if requires_review
                    else []
                ),
            ],
        },
        "notes": _notes(
            record,
            ambiguous_generic,
            source,
            contextual_mechanism,
            joint_amendment_vote,
        ),
    }


def official_data_hash(record: dict[str, Any]) -> str:
    """Hash reproduzível dos campos oficiais usados pelo classificador."""

    payload = {
        "house": record.get("house"),
        "votingId": record.get("votingId"),
        "description": record.get("description"),
        "result": record.get("result"),
        "proposalReferences": record.get("proposalReferences"),
        "possibleObjects": record.get("possibleObjects"),
        "registeredEffects": record.get("registeredEffects"),
        "affectedProposals": record.get("affectedProposals"),
        "latestVotingOpening": record.get("latestVotingOpening"),
        "event": record.get("event"),
        "organ": record.get("organ"),
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _classify_voting_type(
    description: str,
    opening: str,
) -> tuple[str, str | None, str | None, str | None]:
    # Primeiro classificamos o objeto explicitamente deliberado na descrição.
    # Menções incidentais ("ressalvado o destaque", "recurso contra emenda")
    # não podem tomar precedência sobre o núcleo da decisão.
    # Uma PEC aprovada "na forma da Emenda Aglutinativa" ou cuja abertura
    # explicita a votação da emenda não é texto-base original. Substitutiva
    # continua sendo tratada antes como SUBSTITUTE_TEXT.
    if re.search(
        r"\bsubemenda substitutiva\b|\bemenda aglutinativa substitutiva\b|"
        r"^(?:aprovad|rejeitad).{0,40}\b(?:o|a) substitutiv[oa]\b",
        description,
        re.IGNORECASE,
    ):
        return "SUBSTITUTE_TEXT", "R04_SUBSTITUTE", "description", description
    if re.search(
        r"\bna forma da emenda aglutinativa\b",
        description,
        re.IGNORECASE,
    ):
        return "AMENDMENT", "R05_AGGLUTINATIVE", "description", description
    if re.search(
        r"\bvota[cç][aã]o\b.{0,50}\bemenda aglutinativa\b",
        opening,
        re.IGNORECASE,
    ):
        return "AMENDMENT", "R05_AGGLUTINATIVE", "opening", opening

    description_rules = (
        ("FINAL_WORDING", "R01_FINAL_WORDING", r"\breda[cç][aã]o final\b"),
        ("URGENCY_REQUEST", "R02_URGENCY", r"\brequerimento\b.{0,80}\burg[êe]ncia\b|\burg[êe]ncia\b.{0,80}\brequerimento\b"),
        ("REQUIREMENT", "R06_REQUIREMENT", r"\brequerimento\b|\brecurso\b"),
        ("BASE_TEXT", "R09_BASE_TEXT", r"\b(?:projeto de lei(?: complementar)?|proposta de emenda [àa] constitui[cç][aã]o|medida provis[oó]ria|projeto de decreto legislativo)\b"),
        ("OTHER_PROCEDURAL", "R07_PROCEDURAL", r"\bprefer[êe]ncia\b|\badiamento\b|\bretirada de pauta\b|\bencerramento da discuss[aã]o\b"),
        ("OTHER_SUBSTANTIVE", "R08_PRELIMINARY", r"\baprecia[cç][aã]o preliminar\b|\bpressupostos constitucionais\b"),
        ("AMENDMENT", "R05_AMENDMENT", r"\bemendas?\b|\bsubemendas?\b"),
        ("HIGHLIGHT", "R03_HIGHLIGHT", r"\bdtq\b|\bdestaque para vota[cç][aã]o\b|\bvota[cç][aã]o em separado\b"),
    )

    # "Mantido o texto" e "Resultado" são deliberadamente insuficientes;
    # nesses casos a abertura pode sugerir o objeto, mas exige revisão humana.
    generic_description = _is_generic_description(description)
    needs_opening = bool(
        re.match(r"^(?:mantido o texto|resultado)\b", description, re.IGNORECASE)
    )
    if not needs_opening:
        for voting_type, rule_id, pattern in description_rules:
            if re.search(pattern, description, re.IGNORECASE):
                return voting_type, rule_id, "description", description

    opening_rules = (
        ("FINAL_WORDING", "R01_FINAL_WORDING", r"\bvota[cç][aã]o da reda[cç][aã]o final\b"),
        ("URGENCY_REQUEST", "R02_URGENCY", r"\burg[êe]ncia\b"),
        ("HIGHLIGHT", "R03_HIGHLIGHT", r"\bdtq\b|\bdestaque para vota[cç][aã]o\b|\bvota[cç][aã]o em separado\b"),
        ("AMENDMENT", "R05_AMENDMENT", r"\bvota[cç][aã]o d(?:a|as|o|os)\b.{0,30}\b(?:emenda|subemenda)s?\b"),
        ("SUBSTITUTE_TEXT", "R04_SUBSTITUTE", r"\bvota[cç][aã]o\b.{0,40}\bsubstitutiv[oa]\b"),
        ("REQUIREMENT", "R06_REQUIREMENT", r"\bvota[cç][aã]o\b.{0,40}\b(?:requerimento|recurso)\b"),
    )
    if needs_opening:
        for voting_type, rule_id, pattern in opening_rules:
            if re.search(pattern, opening, re.IGNORECASE):
                return voting_type, rule_id, "opening", opening
    return "UNKNOWN", None, None, None


def _classify_stage(
    description: str,
    opening: str,
) -> tuple[str, tuple[str, str] | None]:
    """Só atribui turno quando uma fonte oficial o declara explicitamente.

    Para SINGLE_ROUND, a abertura precisa dizer que se trata de uma votação em
    turno único. Uma menção genérica a tramitação em turno único não basta.
    """

    for source_field, text in (
        ("description", description),
        ("latestVotingOpening.description", opening),
    ):
        for stage, pattern in (
            ("FIRST_ROUND", r"\bprimeiro turno\b"),
            ("SECOND_ROUND", r"\bsegundo turno\b"),
        ):
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return stage, (source_field, match.group(0))

    match = re.search(r"\bturno [úu]nico\b", description, re.IGNORECASE)
    if match:
        return "SINGLE_ROUND", ("description", match.group(0))

    single_round_vote = re.search(
        r"\bvota[cç][aã]o\b.{0,100}\bturno [úu]nico\b|"
        r"\bturno [úu]nico\b.{0,100}\bvota[cç][aã]o\b",
        opening,
        re.IGNORECASE,
    )
    if single_round_vote:
        return (
            "SINGLE_ROUND",
            ("latestVotingOpening.description", single_round_vote.group(0)),
        )
    return "UNKNOWN", None


def _classify_decision_role(
    voting_type: str,
    text_form: str,
    description: str,
    opening: str,
) -> str:
    """Classifica o papel da decisão, sem alterar o objeto da votação."""

    if voting_type in {"REQUIREMENT", "URGENCY_REQUEST", "OTHER_PROCEDURAL"}:
        return "PROCEDURAL_DECISION"
    if voting_type in {"HIGHLIGHT", "FINAL_WORDING"}:
        return "PARTIAL_TEXT_DECISION"
    if voting_type == "AMENDMENT":
        # Uma emenda normalmente é parcial. Exceção: a descrição oficial pode
        # declarar que a própria PEC foi decidida no turno "na forma" dela.
        if text_form == "AGGLUTINATIVE_AMENDMENT" and re.search(
            r"\bproposta de emenda [àa] constitui[cç][aã]o\b.*"
            r"\bna forma da emenda aglutinativa\b",
            description,
            re.IGNORECASE,
        ):
            return "MAIN_PROPOSAL_DECISION"
        if (
            re.search(r"\baprova(?:d[oa]s?|[cç][aã]o)\b", description, re.IGNORECASE)
            and re.search(
                r"\bproposta de emenda [àa] constitui[cç][aã]o\b",
                description,
                re.IGNORECASE,
            )
            and re.search(
                r"\b(?:primeiro|segundo) turno\b", description, re.IGNORECASE
            )
            and re.search(r"\bemenda aglutinativa\b", opening, re.IGNORECASE)
        ):
            return "MAIN_PROPOSAL_DECISION"
        return "PARTIAL_TEXT_DECISION"
    if voting_type == "SUBSTITUTE_TEXT":
        if re.search(
            r"\bproposta de emenda [àa] constitui[cç][aã]o\b.*"
            r"\bna forma da emenda aglutinativa substitutiva\b",
            description,
            re.IGNORECASE,
        ):
            return "MAIN_PROPOSAL_DECISION"
        # Um substitutivo explicitamente aprovado ocupa o lugar do texto-base.
        if re.search(r"\baprova(?:d[oa]s?|[cç][aã]o)\b", description, re.IGNORECASE):
            return "MAIN_PROPOSAL_DECISION"
        return "INDETERMINATE"
    if voting_type == "BASE_TEXT":
        return "MAIN_PROPOSAL_DECISION"
    if voting_type in {"UNKNOWN", "OTHER_SUBSTANTIVE"}:
        return "INDETERMINATE"
    return "INDETERMINATE"


def _classify_result(description: str) -> tuple[str, str | None]:
    rules = (
        ("REJECTED", r"\brejeitad[oa]s?\b|\bn[aã]o aprovado\b"),
        ("MAINTAINED", r"\bmantid[oa]s?\b"),
        ("APPROVED", r"\baprova(?:d[oa]s?|[cç][aã]o)\b"),
    )
    for result, pattern in rules:
        match = re.search(pattern, description, re.IGNORECASE)
        if match:
            return result, description
    return "UNKNOWN", None


def _text_decision_status(voting_type: str, source: str | None) -> str:
    if voting_type in {"URGENCY_REQUEST", "REQUIREMENT", "OTHER_PROCEDURAL"}:
        return "NOT_TEXT_DECISION"
    if voting_type in {
        "AMENDMENT",
        "HIGHLIGHT",
        "SUBSTITUTE_TEXT",
        "BASE_TEXT",
        "FINAL_WORDING",
    }:
        return (
            "TEXT_DECISION_CONFIRMED"
            if source == "description"
            else "TEXT_DECISION_POSSIBLE"
        )
    if voting_type == "OTHER_SUBSTANTIVE":
        return "TEXT_DECISION_POSSIBLE"
    return "INDETERMINATE"


def _classify_text_form(
    voting_type: str,
    description: str,
    opening: str,
) -> str:
    text = f"{description} {opening}"
    if voting_type == "SUBSTITUTE_TEXT":
        return "SUBSTITUTE_OR_SUBAMENDMENT"
    if voting_type == "AMENDMENT" and re.search(
        r"\bemenda aglutinativa\b",
        text,
        re.IGNORECASE,
    ):
        return "AGGLUTINATIVE_AMENDMENT"
    if voting_type == "BASE_TEXT" and re.search(
        r"\bprojeto de lei de convers[aã]o\b|\bPLV\b",
        text,
        re.IGNORECASE,
    ):
        return "CONVERSION_BILL"
    if voting_type == "BASE_TEXT":
        return "ORIGINAL_OR_UNQUALIFIED"
    return "NOT_APPLICABLE"


def _contextual_mechanism(voting_type: str, opening: str) -> str | None:
    if voting_type == "AMENDMENT" and re.search(
        r"\bdtq\b|\bdestaque\b",
        opening,
        re.IGNORECASE,
    ):
        return "HIGHLIGHT_OR_DTQ"
    return None


def _individual_vote_availability(record: dict[str, Any]) -> str:
    bindings = (record.get("rawMetadata") or {}).get("storedBindings") or []
    totals = [
        int((item.get("voting") or {}).get("totalRecordedVotes") or 0)
        for item in bindings
    ]
    if any(total > 0 for total in totals):
        return "AVAILABLE_IN_ARCHIVED_BINDING"
    urls = [
        ref
        for ref in record.get("officialReferences", [])
        if str(ref).rstrip("/").endswith("/votos")
    ]
    if urls:
        return "OFFICIAL_ENDPOINT_REFERENCED_NOT_VERIFIED"
    return "UNKNOWN"


def _is_generic_description(description: str) -> bool:
    normalized = re.sub(r"\s+", " ", description.strip().casefold())
    return bool(
        re.match(
            r"^(?:rejeitado o requerimento|aprovado o requerimento|mantido o texto|resultado)\b",
            normalized,
        )
    )


def _is_joint_amendment_vote(description: str) -> bool:
    """Detecta uma deliberação agregada sem identificar cada emenda."""

    return bool(
        re.search(
            r"\b(?:as|das) emendas(?: de plen[áa]rio)?\b",
            description,
            re.IGNORECASE,
        )
        and not re.search(r"\bemenda\s+(?:n[º°o]\s*)?\d+\b", description, re.IGNORECASE)
    )


def _notes(
    record: dict[str, Any],
    ambiguous_generic: bool,
    source: str | None,
    contextual_mechanism: str | None,
    joint_amendment_vote: bool,
) -> str | None:
    notes = []
    if ambiguous_generic:
        notes.append("Descrição genérica: exige contexto oficial adicional.")
    if source == "opening":
        notes.append("Tipo sugerido pela abertura, não pela descrição principal.")
    if len(record.get("proposalReferences", [])) > 1:
        notes.append("Há vários vínculos; nenhum foi promovido a objeto automaticamente.")
    if contextual_mechanism:
        notes.append(
            "A decisão recai sobre emenda, enquanto a abertura registra "
            "destaque/DTQ como mecanismo; exige validação humana."
        )
    if joint_amendment_vote:
        notes.append(
            "Votação conjunta de múltiplas emendas sem individualização: "
            "revisão humana obrigatória."
        )
    return " ".join(notes) or None


def _voting_reference(record: dict[str, Any]) -> str | None:
    refs = record.get("officialReferences") or []
    return str(refs[0]) if refs else None


def _source_fetched_at(record: dict[str, Any]) -> str | None:
    return (record.get("rawMetadata") or {}).get("officialResponseFetchedAt")


def _clean(value: Any) -> str:
    return str(value).strip() if value is not None else ""

