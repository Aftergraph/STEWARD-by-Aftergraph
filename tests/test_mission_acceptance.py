import unittest

from steward.ports.mission_acceptance import (
    MissionAcceptanceContractError,
    MissionAcceptancePort,
    MissionAcceptanceRequest,
)

WORK="wrk_"+"1"*32
MISSION="mis_p2"
CTX="ctx_"+"2"*32
PDR="pdr_"+"3"*32

class Reader:
    def __init__(self,payload): self.payload=payload
    def get_evidence(self,work_id): return self.payload

def req():
    return MissionAcceptanceRequest(
        mission_id=MISSION,
        work_id=WORK,
        execution_context_id=CTX,
        execution_policy_decision_id=PDR,
    )

def payload(status="verified", outcome="passed"):
    return {
        "bundle_id":"evb_"+"a"*32,
        "work_id":WORK,
        "identity_chain":{
            "mission_id":MISSION,
            "work_id":WORK,
            "execution_context_id":CTX,
            "execution_policy_decision_id":PDR,
        },
        "platform_outcome_verification":{
            "status":status,
            "outcome_status":outcome,
        },
    }

class MissionAcceptanceTests(unittest.TestCase):
    def test_accepts_only_verified_passed_projection(self):
        out=MissionAcceptancePort(Reader(payload())).project(req())
        self.assertTrue(out.accepted)
        self.assertEqual("verified",out.status)

    def test_pending_never_accepts(self):
        out=MissionAcceptancePort(Reader(payload("pending","pending"))).project(req())
        self.assertFalse(out.accepted)

    def test_provenance_gap_never_accepts(self):
        out=MissionAcceptancePort(Reader(payload("provenance_gap","passed"))).project(req())
        self.assertFalse(out.accepted)

    def test_identity_chain_mismatch_fails_closed(self):
        bad=payload()
        bad["identity_chain"]["execution_context_id"]="ctx_"+"f"*32
        with self.assertRaisesRegex(MissionAcceptanceContractError,"execution_context_id"):
            MissionAcceptancePort(Reader(bad)).project(req())

    def test_work_rebind_fails_closed(self):
        bad=payload()
        bad["work_id"]="wrk_"+"f"*32
        with self.assertRaisesRegex(MissionAcceptanceContractError,"another Work"):
            MissionAcceptancePort(Reader(bad)).project(req())

if __name__=="__main__":
    unittest.main()
