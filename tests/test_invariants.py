import unittest

class InvariantTests(unittest.TestCase):
    def test_child_delegation_must_be_attenuated(self):
        parent_caps = {'repo.read', 'repo.write', 'pr.create'}
        child_caps = {'repo.read', 'repo.write'}
        self.assertTrue(child_caps <= parent_caps)
        self.assertFalse({'repo.read', 'repo.admin'} <= parent_caps)

    def test_selected_is_not_authorized(self):
        selected = True
        authority_grant = False
        executable = selected and authority_grant
        self.assertFalse(executable)

    def test_completed_is_not_verified(self):
        worker_completed = True
        independent_verification = False
        accepted = worker_completed and independent_verification
        self.assertFalse(accepted)

if __name__ == '__main__':
    unittest.main()
