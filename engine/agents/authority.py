from __future__ import annotations

from dataclasses import dataclass

from .models import AgentContract, AgentProposal, AgentResult, AgentStatus, ProposalKind


@dataclass(frozen=True)
class AuthorityDecision:
    allowed: bool
    reason: str


class AgentAuthority:
    """Checks agent proposals without applying them to authoritative state."""

    def validate_contract(self, contract: AgentContract) -> AuthorityDecision:
        if not contract.chat_enabled:
            return AuthorityDecision(False, "Agent conversation is disabled by contract.")
        return AuthorityDecision(True, "Contract is valid.")

    def validate_proposal(
        self,
        contract: AgentContract,
        proposal: AgentProposal,
    ) -> AuthorityDecision:
        if proposal.agent_id != contract.agent_id:
            return AuthorityDecision(False, "Proposal agent_id does not match the contract.")

        if proposal.kind == ProposalKind.STATE_INTERVENTION:
            if "intervention.propose" not in contract.write_scopes:
                return AuthorityDecision(False, "Agent lacks intervention.propose scope.")
            if not proposal.requires_approval:
                return AuthorityDecision(False, "State interventions always require human approval.")
            return AuthorityDecision(True, "Intervention proposal may enter the intervention planner.")

        if proposal.kind == ProposalKind.NARRATIVE_EDIT:
            if "narrative.draft" not in contract.write_scopes:
                return AuthorityDecision(False, "Agent lacks narrative.draft scope.")
            return AuthorityDecision(True, "Narrative draft is non-authoritative.")

        if proposal.kind in {ProposalKind.OBSERVATION, ProposalKind.RECOMMENDATION}:
            return AuthorityDecision(True, "Non-authoritative proposal accepted.")

        return AuthorityDecision(False, "Unknown proposal kind.")

    def gate_result(self, contract: AgentContract, result: AgentResult) -> AgentResult:
        accepted = []
        blocked = list(result.diagnostics)

        for proposal in result.proposals:
            decision = self.validate_proposal(contract, proposal)
            if decision.allowed:
                accepted.append(proposal)
            else:
                blocked.append(decision.reason)

        status = result.status
        if len(accepted) != len(result.proposals):
            status = AgentStatus.BLOCKED

        return AgentResult(
            status=status,
            response=result.response,
            proposals=accepted,
            diagnostics=blocked,
        )
