from pathlib import Path
import subprocess
import tempfile
import unittest


def run(cwd, *args):
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def call(cwd, *args):
    subprocess.check_call(args, cwd=cwd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class GitWorktreeExactHeadTests(unittest.TestCase):
    def test_isolated_worktree_and_verdict_invalidation(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = root / 'repo'
            worktree = root / 'wt-builder'
            review = root / 'wt-review'
            repo.mkdir()
            call(repo, 'git', 'init', '-b', 'main')
            call(repo, 'git', 'config', 'user.name', 'Steward Test')
            call(repo, 'git', 'config', 'user.email', 'steward-test@aftergraph.org')
            (repo / 'subject.txt').write_text('base\n', encoding='utf-8')
            call(repo, 'git', 'add', 'subject.txt')
            call(repo, 'git', 'commit', '-m', 'base')
            base = run(repo, 'git', 'rev-parse', 'HEAD')

            call(repo, 'git', 'worktree', 'add', '-b', 'feat/p1', str(worktree), base)
            (worktree / 'subject.txt').write_text('base\nverified change\n', encoding='utf-8')
            call(worktree, 'git', 'add', 'subject.txt')
            call(worktree, 'git', 'commit', '-m', 'verified candidate')
            sha_a = run(worktree, 'git', 'rev-parse', 'HEAD')

            call(repo, 'git', 'worktree', 'add', '--detach', str(review), sha_a)
            review_head = run(review, 'git', 'rev-parse', 'HEAD')
            self.assertEqual(sha_a, review_head)
            self.assertNotEqual(repo.resolve(), worktree.resolve())
            self.assertNotEqual(worktree.resolve(), review.resolve())

            verdict_subject = sha_a
            (worktree / 'subject.txt').write_text('base\nverified change\npost-verdict mutation\n', encoding='utf-8')
            call(worktree, 'git', 'add', 'subject.txt')
            call(worktree, 'git', 'commit', '-m', 'mutate after verdict')
            sha_b = run(worktree, 'git', 'rev-parse', 'HEAD')

            self.assertNotEqual(sha_a, sha_b)
            self.assertNotEqual(verdict_subject, sha_b, 'Verdict for SHA A must be stale for SHA B')
            self.assertEqual(verdict_subject, run(review, 'git', 'rev-parse', 'HEAD'))

if __name__ == '__main__':
    unittest.main()
