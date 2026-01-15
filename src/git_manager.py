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
