import unittest

from classifier import classify_record, official_data_hash


def record(description: str, opening: str | None = None) -> dict:
    return {
        "house": "CAMARA",
        "votingId": "test-1",
        "description": description,
        "result": {"originalApprovalIndicator": None},
        "proposalReferences": [
            {"id": "10", "identification": "PL 1/2026", "relation": "TEST"}
        ],
        "possibleObjects": [],
        "registeredEffects": [],
        "affectedProposals": [],
        "latestVotingOpening": {"description": opening, "registrationDateTime": None},
        "event": {"id": "1", "uri": None},
        "organ": {"id": "180", "acronym": "PLEN", "uri": None},
        "officialReferences": ["https://example.test/votacoes/test-1"],
        "rawMetadata": {
            "officialResponseFetchedAt": "2026-01-01T00:00:00Z",
            "storedBindings": [],
        },
    }


class ClassifierTests(unittest.TestCase):
    def test_urgency_precedes_generic_requirement(self) -> None:
        output = classify_record(
            record("Aprovado o Requerimento de Urgência (Art. 155 do RICD).")
        )
        self.assertEqual(output["classification"]["votingType"], "URGENCY_REQUEST")
        self.assertEqual(
            output["classification"]["textDecisionStatus"], "NOT_TEXT_DECISION"
        )

    def test_substitute_precedes_amendment(self) -> None:
        output = classify_record(
            record("Aprovada a Subemenda Substitutiva ao Projeto de Lei.")
        )
        self.assertEqual(output["classification"]["votingType"], "SUBSTITUTE_TEXT")

    def test_reserved_highlight_does_not_replace_substitute_object(self) -> None:
        output = classify_record(
            record(
                "Aprovada a Subemenda Substitutiva ao Projeto de Lei, "
                "ressalvado o destaque."
            )
        )
        self.assertEqual(output["classification"]["votingType"], "SUBSTITUTE_TEXT")

    def test_constitutional_amendment_proposal_is_base_text(self) -> None:
        output = classify_record(
            record(
                "Aprovada, em segundo turno, a Proposta de Emenda à "
                "Constituição nº 5, de 2023."
            )
        )
        self.assertEqual(output["classification"]["votingType"], "BASE_TEXT")

    def test_appeal_against_amendment_is_requirement_family(self) -> None:
        output = classify_record(
            record("Rejeitado o Recurso contra parecer relativo à Emenda nº 3.")
        )
        self.assertEqual(output["classification"]["votingType"], "REQUIREMENT")

    def test_plain_amendment_descriptions_are_not_unknown(self) -> None:
        descriptions = [
            "Rejeitada a Emenda n° 102. Sim: 22; Não: 378; Total: 400.",
            "Rejeitadas as Emendas de Plenário.",
            "Rejeitada a Emenda nº 99.",
            "Rejeitada a Emenda n° 2.",
            "Rejeitada a Emenda nº 96.",
            "Rejeitada a Emenda nº 97.",
        ]
        for description in descriptions:
            with self.subTest(description=description):
                output = classify_record(record(description))
                self.assertEqual(
                    output["classification"]["votingType"],
                    "AMENDMENT",
                )

    def test_amendment_voted_through_highlight_preserves_both_axes(self) -> None:
        output = classify_record(
            record(
                "Rejeitada a Emenda nº 99.",
                "Votação do DTQ 8: Destaque da Emenda nº 99.",
            )
        )
        self.assertEqual(output["classification"]["votingType"], "AMENDMENT")
        self.assertEqual(
            output["classification"]["contextualMechanism"],
            "HIGHLIGHT_OR_DTQ",
        )
        self.assertTrue(output["classification"]["requiresHumanReview"])

    def test_base_text_forms_are_distinguished(self) -> None:
        original = classify_record(record("Aprovado o Projeto de Lei nº 1."))
        agglutinative = classify_record(
            record(
                "Aprovada a Proposta de Emenda à Constituição nº 1, "
                "na forma da Emenda Aglutinativa nº 2."
            )
        )
        substitute = classify_record(
            record("Aprovada a Subemenda Substitutiva ao Projeto de Lei nº 1.")
        )
        conversion = classify_record(
            record(
                "Aprovada a Medida Provisória nº 1, na forma do Projeto de "
                "Lei de Conversão."
            )
        )

        self.assertEqual(original["classification"]["votingType"], "BASE_TEXT")
        self.assertEqual(
            original["classification"]["textForm"],
            "ORIGINAL_OR_UNQUALIFIED",
        )
        self.assertEqual(
            agglutinative["classification"]["votingType"],
            "AMENDMENT",
        )
        self.assertEqual(
            agglutinative["classification"]["textForm"],
            "AGGLUTINATIVE_AMENDMENT",
        )
        self.assertEqual(
            substitute["classification"]["votingType"],
            "SUBSTITUTE_TEXT",
        )
        self.assertEqual(
            substitute["classification"]["textForm"],
            "SUBSTITUTE_OR_SUBAMENDMENT",
        )
        self.assertEqual(conversion["classification"]["votingType"], "BASE_TEXT")
        self.assertEqual(
            conversion["classification"]["textForm"],
            "CONVERSION_BILL",
        )

    def test_final_wording_precedes_base_text(self) -> None:
        output = classify_record(
            record("Aprovada a Redação Final do Projeto de Lei nº 1.")
        )
        self.assertEqual(output["classification"]["votingType"], "FINAL_WORDING")

    def test_generic_maintained_text_abstains(self) -> None:
        output = classify_record(record("Mantido o texto."))
        self.assertEqual(output["classification"]["votingType"], "UNKNOWN")
        self.assertTrue(output["classification"]["requiresHumanReview"])

    def test_generic_requirement_keeps_only_requirement_family(self) -> None:
        output = classify_record(
            record("Rejeitado o Requerimento. Sim: 100; Não: 200; Total: 300.")
        )
        self.assertEqual(output["classification"]["votingType"], "REQUIREMENT")
        self.assertTrue(output["classification"]["requiresHumanReview"])

    def test_opening_can_propose_highlight_but_requires_review(self) -> None:
        output = classify_record(
            record(
                "Mantido o texto.",
                "Votação do DTQ 2: destaque para votação em separado do art. 7º.",
            )
        )
        self.assertEqual(output["classification"]["votingType"], "HIGHLIGHT")
        self.assertEqual(
            output["classification"]["textDecisionStatus"],
            "TEXT_DECISION_POSSIBLE",
        )
        self.assertTrue(output["classification"]["requiresHumanReview"])

    def test_stage_is_only_set_from_explicit_text(self) -> None:
        explicit = classify_record(
            record("Aprovada, em segundo turno, a Proposta de Emenda à Constituição.")
        )
        absent = classify_record(record("Aprovado o Projeto de Lei."))
        self.assertEqual(explicit["classification"]["legislativeStage"], "SECOND_ROUND")
        self.assertEqual(absent["classification"]["legislativeStage"], "UNKNOWN")

    def test_single_round_requires_explicit_voting_evidence(self) -> None:
        explicit = classify_record(
            record(
                "Aprovado o Projeto de Lei.",
                "Votação, quanto ao mérito, em turno único.",
            )
        )
        insufficient = classify_record(
            record("Aprovado o Projeto de Lei.", "Tramitação em turno único.")
        )
        self.assertEqual(
            explicit["classification"]["legislativeStage"], "SINGLE_ROUND"
        )
        self.assertEqual(
            insufficient["classification"]["legislativeStage"], "UNKNOWN"
        )

    def test_decision_role_keeps_object_and_role_as_separate_axes(self) -> None:
        output = classify_record(
            record(
                "Aprovada, em primeiro turno, a Proposta de Emenda à "
                "Constituição nº 383, de 2017, na forma da Emenda "
                "Aglutinativa nº 2."
            )
        )
        self.assertEqual(output["classification"]["votingType"], "AMENDMENT")
        self.assertEqual(
            output["classification"]["decisionRole"],
            "MAIN_PROPOSAL_DECISION",
        )
        self.assertEqual(
            output["classification"]["legislativeStage"], "FIRST_ROUND"
        )

    def test_substitutive_agglutinative_can_be_main_turn_decision(self) -> None:
        output = classify_record(
            record(
                "Aprovada, em primeiro turno, a Proposta de Emenda à "
                "Constituição nº 5, de 2023, na forma da Emenda "
                "Aglutinativa Substitutiva nº 3."
            )
        )
        self.assertEqual(output["classification"]["votingType"], "SUBSTITUTE_TEXT")
        self.assertEqual(
            output["classification"]["decisionRole"],
            "MAIN_PROPOSAL_DECISION",
        )

    def test_agglutinative_opening_preserves_main_pec_decision_with_review(self) -> None:
        output = classify_record(
            record(
                "Aprovada, em primeiro turno, a Proposta de Emenda à "
                "Constituição nº 221, de 2019.",
                "Votação da Emenda Aglutinativa nº 1.",
            )
        )
        self.assertEqual(output["classification"]["votingType"], "AMENDMENT")
        self.assertEqual(
            output["classification"]["decisionRole"],
            "MAIN_PROPOSAL_DECISION",
        )
        self.assertTrue(output["classification"]["requiresHumanReview"])

    def test_second_round_base_text_is_main_decision(self) -> None:
        output = classify_record(
            record(
                "Aprovada, em segundo turno, a Proposta de Emenda à "
                "Constituição nº 221, de 2019."
            )
        )
        self.assertEqual(output["classification"]["votingType"], "BASE_TEXT")
        self.assertEqual(
            output["classification"]["decisionRole"],
            "MAIN_PROPOSAL_DECISION",
        )

    def test_highlight_is_partial_text_decision(self) -> None:
        output = classify_record(
            record(
                "Mantido o texto.",
                "Votação do DTQ 5: Destaque para Votação em Separado do art. 1º.",
            )
        )
        self.assertEqual(
            output["classification"]["decisionRole"],
            "PARTIAL_TEXT_DECISION",
        )

    def test_joint_amendments_require_human_review(self) -> None:
        output = classify_record(record("Rejeitadas as Emendas de Plenário."))
        self.assertEqual(output["classification"]["votingType"], "AMENDMENT")
        self.assertEqual(
            output["classification"]["decisionRole"],
            "PARTIAL_TEXT_DECISION",
        )
        self.assertTrue(output["classification"]["requiresHumanReview"])
        self.assertIn("Votação conjunta", output["notes"])

    def test_hash_is_stable_and_changes_with_official_input(self) -> None:
        first = record("Aprovado o Projeto de Lei.")
        second = record("Aprovado o Projeto de Lei.")
        self.assertEqual(official_data_hash(first), official_data_hash(second))
        second["description"] = "Rejeitado o Projeto de Lei."
        self.assertNotEqual(official_data_hash(first), official_data_hash(second))

    def test_prototype_output_is_never_marked_publishable(self) -> None:
        output = classify_record(record("Aprovado o Projeto de Lei nº 1."))
        self.assertEqual(
            output["annotationStatus"],
            "AUTOMATIC_PROPOSAL_NOT_HUMAN_VALIDATED",
        )
        self.assertEqual(
            output["publication"]["eligibility"],
            "BLOCKED_PENDING_REVIEW",
        )


if __name__ == "__main__":
    unittest.main()
