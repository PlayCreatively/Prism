import subprocess
from typing import Optional


class GitManager:
    """
    A small helper for running common git automations used by the application.

    Methods:
    - pull_rebase(): Runs `git pull --rebase`.
    - add_all(): Runs `git add .`.
    - commit(message): Runs `git commit -m <message>`.
    - push(): Runs `git push`.
    - push_changes(user): Runs add, commit with message "Update by <user>", then push.
    """

    def __init__(self, repo_path: Optional[str] = None):
        """
        :param repo_path: Optional path to the git repository. If None, commands run in current working directory.
        """
        self.repo_path = repo_path

    def _run(self, args):
        """
        Internal wrapper around subprocess.run to execute git commands.

        :param args: List of command arguments (e.g. ['git', 'pull', '--rebase'])
        :return: subprocess.CompletedProcess
        :raises: subprocess.CalledProcessError if the command fails (check=True)
        """
        return subprocess.run(
            args,
            cwd=self.repo_path,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

    def pull_rebase(self):
        """
        Perform `git pull --rebase`.
        """
        return self._run(['git', 'pull', '--rebase'])

    def add_all(self):
        """
        Perform `git add .`.
        """
        return self._run(['git', 'add', '.'])

    def commit(self, message: str):
        """
        Perform `git commit -m <message>`.
        """
        return self._run(['git', 'commit', '-m', message])

    def push(self):
        """
        Perform `git push`.
        """
        return self._run(['git', 'push'])

    def has_changes(self, user: str) -> bool:
        """
        Check if there are any uncommitted changes relevant to the user.
        This includes:
        1. Modifications to data/{user}.json
        2. New files in mutations/
        """
        # git status --porcelain gives a clean parsable output
        res = self._run(['git', 'status', '--porcelain'])
        if res.stdout:
            lines = res.stdout.strip().split('\n')
            for line in lines:
                # Format is "XY Path/To/File"
                # We care about modifications or untracked files
                parts = line.strip().split()
                if len(parts) < 2: continue
                path = parts[-1]
                
                # Check 1: Creating/Modifying mutations
                if 'mutations' in path: 
                    return True
                
                # Check 2: Modifying own user file
                # Path normalization might differ on OS, check substring safely
                if f"{user}.json" in path or f"{user.lower()}.json" in path:
                    return True
                    
        return False

    def stage_user_changes(self, user: str):
        """
        Stage only the files relevant to the user.
        """
        # 1. Stage the user's data file
        # The path is relative to the git repo root. 
        # If GitManager is initialized with repo_path="db", and db contains "data", this works.
        self._run(['git', 'add', f'data/{user}.json'])
        
        # 2. Stage all mutations (new or modified)
        # It's generally safe to add all mutations as they are append-only logs usually
        self._run(['git', 'add', 'mutations/'])

    def push_changes_for_user(self, user: str):
        """
        Stage user-specific changes, commit, and push.
        """
        self.stage_user_changes(user)
        # Check if anything was actually staged? git commit will fail if empty, which is fine to catch or handle
        try:
            self.commit(f'Update by {user}')
            self.pull_rebase()
            self.push()
            return True
        except subprocess.CalledProcessError:
            # Likely nothing to commit
            return False

    def push_changes(self, user: str):
        """
        Convenience routine to add all changes, commit with a standardized message,
        and push to the remote.

        :param user: The user name to include in the commit message.
        :return: A tuple of CompletedProcess results (add_result, commit_result, push_result)
        """
        add_result = self.add_all()
        commit_result = self.commit(f'Update by {user}')
        push_result = self.push()
        return add_result, commit_result, push_result

    def is_repo(self) -> bool:
        """Check if the current directory is a git repository."""
        try:
            self._run(['git', 'rev-parse', '--is-inside-work-tree'])
            return True
        except subprocess.CalledProcessError:
            return False

    def get_config(self, key: str) -> Optional[str]:
        """Get a specific git config value."""
        try:
            res = self._run(['git', 'config', key])
            return res.stdout.strip()
        except subprocess.CalledProcessError:
            return None

    def validate_setup(self) -> dict:
        """
        Run a health check on the git setup.
        Returns a dict with 'ok' (bool) and 'issues' (list of strings).
        """
        issues = []
        if not self.is_repo():
            return {'ok': False, 'issues': ['Not a valid git repository']}

        # Check user config
        if not self.get_config('user.name'):
            issues.append('Git user.name not configured')
        if not self.get_config('user.email'):
            issues.append('Git user.email not configured')
        
        # Check remote
        try:
            self._run(['git', 'remote', 'get-url', 'origin'])
        except subprocess.CalledProcessError:
            issues.append('No remote "origin" configured')

        return {'ok': len(issues) == 0, 'issues': issues}
