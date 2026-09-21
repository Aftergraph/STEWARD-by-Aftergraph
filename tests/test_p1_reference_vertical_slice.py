from pathlib import Path
import sys
import unittest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from steward_reference.vertical_slice import ReferenceVerticalSlice

class P1ReferenceVerticalSliceTests(unittest.TestCase):
    def test_goal_to_exact_head_verified_acceptance(self):
        result = ReferenceVerticalSlice().run()
        self.assertTrue(result.tests_passed)
        self.assertEqual('PASS', result.verification.verdict)
        self.assertEqual(result.candidate_sha, result.verification.subject_sha)
        self.assertEqual(result.candidate_sha, result.verifier_sha)
        self.assertTrue(result.mission_accepted)
        kinds = [event.kind for event in result.trace]
        self.assertIn('git.baseline', kinds)
        self.assertIn('worktree.provisioned', kinds)
        self.assertIn('test.failed', kinds)
        self.assertIn('test.passed', kinds)
        self.assertIn('git.commit', kinds)
        self.assertIn('verification.verdict', kinds)
        self.assertEqual('mission.acceptance', kinds[-1])

if __name__ == '__main__':
    unittest.main()
