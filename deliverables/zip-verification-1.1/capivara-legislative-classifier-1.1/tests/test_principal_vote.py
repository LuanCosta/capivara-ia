import unittest

from principal_vote import select_principal_votes


def classification(voting_id, stage, review=False, role="MAIN_PROPOSAL_DECISION"):
    return {
        "votingId": voting_id,
        "classification": {
            "decisionRole": role,
            "legislativeStage": stage,
            "votingType": "BASE_TEXT",
            "textForm": "ORIGINAL_OR_UNQUALIFIED",
            "requiresHumanReview": review,
        },
    }


def source(voting_id, proposal_ids):
    return {
        "votingId": voting_id,
        "proposalReferences": [{"id": value} for value in proposal_ids],
    }


class PrincipalVoteTests(unittest.TestCase):
    def test_explicit_second_round_is_selected_over_first(self):
        result = select_principal_votes(
            [source("pec-1", ["383"]), source("pec-2", ["383"])],
            [
                classification("pec-1", "FIRST_ROUND"),
                classification("pec-2", "SECOND_ROUND"),
            ],
        )
        selected = result["selections"][0]
        self.assertEqual(selected["status"], "SELECTED_FOR_HUMAN_VALIDATION")
        self.assertEqual(selected["selectedVotingId"], "pec-2")

    def test_tied_main_decisions_are_indeterminate(self):
        result = select_principal_votes(
            [source("a", ["1"]), source("b", ["1"])],
            [classification("a", "SINGLE_ROUND"), classification("b", "SINGLE_ROUND")],
        )
        self.assertEqual(result["selections"][0]["status"], "INDETERMINATE")

    def test_only_procedural_vote_is_indeterminate(self):
        result = select_principal_votes(
            [source("req", ["1"])],
            [classification("req", "UNKNOWN", role="PROCEDURAL_DECISION")],
        )
        self.assertEqual(result["selections"][0]["status"], "INDETERMINATE")

    def test_multiple_proposal_binding_blocks_selection(self):
        result = select_principal_votes(
            [source("joint", ["1", "2"])],
            [classification("joint", "SINGLE_ROUND")],
        )
        self.assertTrue(
            all(item["status"] == "INDETERMINATE" for item in result["selections"])
        )


if __name__ == "__main__":
    unittest.main()
