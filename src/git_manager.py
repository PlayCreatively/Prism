import subprocess
from typing import Optional, Callable, List
import traceback


class GitError(Exception):
    """Custom exception for git operations with detailed context."""
    def __init__(self, message: str, operation: str, stderr: str = "", returncode: int = 0):
        self.operation = operation
        self.stderr = stderr
        self.returncode = returncode
        super().__init__(message)


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

    def __init__(self, repo_path: Optional[str] = None, on_error: Optional[Callable[[str, str], None]] = None):
        """
        :param repo_path: Optional path to the git repository. If None, commands run in current working directory.
        :param on_error: Optional callback for error notifications. Receives (title, message).
        """
        self.repo_path = repo_path
        self._on_error = on_error
        self._errors: List[str] = []  # Collect errors for batch reporting

    def _notify_error(self, title: str, message: str):
        """Internal helper to report errors via callback."""
        error_msg = f"{title}: {message}"
        self._errors.append(error_msg)
        if self._on_error:
            self._on_error(title, message)

    def get_errors(self) -> List[str]:
        """Get and clear collected errors."""
        errors = self._errors.copy()
        self._errors.clear()
        return errors

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
        If it fails due to missing upstream configuration, attempts to configure it and retry.
        Returns: CompletedProcess on success, None if no upstream (new repo), raises GitError on failure.
        """
        try:
            return self._run(['git', 'pull', '--rebase'])
        except subprocess.CalledProcessError as e:
            # 128 often means "No tracking information"
            if e.returncode == 128:
                try:
                    # Try to auto-configure upstream
                    # 1. Get current branch
                    res = self._run(['git', 'branch', '--show-current'])
                    branch = res.stdout.strip()
                    
                    if branch:
                        # 2. Fetch origin to ensure we know about remote branches
                        self._run(['git', 'fetch', 'origin'])
                        
                        # 3. Set upstream
                        self._run(['git', 'branch', '--set-upstream-to', f'origin/{branch}', branch])
                        
                        # 4. Retry pull
                        return self._run(['git', 'pull', '--rebase'])
                except subprocess.CalledProcessError as recovery_error:
                    # Recovery failed - this is expected for new repos without remote branches
                    # Log but don't error - push will create the remote branch
                    self._notify_error(
                        "Git Pull Info",
                        f"No upstream branch yet for '{branch}' - will be created on push"
                    )
                    return None
                except Exception as unexpected:
                    # Unexpected error during recovery
                    self._notify_error(
                        "Git Pull Recovery Failed",
                        f"Unexpected error: {str(unexpected)}\n{traceback.format_exc()}"
                    )
                    return None
                return None
            # Non-128 error - this is a real failure
            error_msg = e.stderr.strip() if e.stderr else str(e)
            self._notify_error("Git Pull Failed", error_msg)
            raise GitError(f"Pull failed: {error_msg}", "pull_rebase", e.stderr, e.returncode)

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
        Perform `git push`. Attempts to set upstream if generic push fails.
        Raises GitError on failure.
        """
        try:
            return self._run(['git', 'push'])
        except subprocess.CalledProcessError as initial_error:
            # Fallback: Try setting upstream for the current branch
            try:
                res = self._run(['git', 'branch', '--show-current'])
                branch = res.stdout.strip()
                if branch:
                    return self._run(['git', 'push', '-u', 'origin', branch])
            except subprocess.CalledProcessError as fallback_error:
                # Both push attempts failed - report the fallback error
                error_msg = fallback_error.stderr.strip() if fallback_error.stderr else str(fallback_error)
                self._notify_error("Git Push Failed", f"Could not push to origin/{branch}: {error_msg}")
                raise GitError(
                    f"Push failed: {error_msg}",
                    "push",
                    fallback_error.stderr,
                    fallback_error.returncode
                )
            except Exception as unexpected:
                # Unexpected error during fallback
                error_msg = str(unexpected)
                self._notify_error("Git Push Failed", f"Unexpected error: {error_msg}")
                raise GitError(f"Push failed unexpectedly: {error_msg}", "push")
            # Re-raise original if we somehow get here
            raise

    def has_changes(self, user: str) -> bool:
        """
        Check if there are any uncommitted changes relevant to the user,
        OR if there are any unpushed committed changes.
        """
        # 1. Check for unpushed commits (Generic)
        try:
            # check against tracked upstream
            # 'git cherry' lists commits that are not in upstream
            res = self._run(['git', 'cherry', '-v'])
            if res.stdout and res.stdout.strip():
                return True
        except subprocess.CalledProcessError as e:
            # Return code 128 = no upstream configured (expected for new repos)
            # Return code 1 = no commits yet (expected for new repos)
            if e.returncode not in (1, 128):
                # Unexpected error - report it
                error_msg = e.stderr.strip() if e.stderr else f"Exit code {e.returncode}"
                self._notify_error("Git Status Check Warning", f"cherry failed: {error_msg}")

        # 2. Check for uncommitted changes (User specific)
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
        
        # 2. Stage node files
        self._run(['git', 'add', 'nodes/'])

    def push_changes_for_user(self, user: str):
        """
        Stage user-specific changes, commit, and push.
        Raises GitError on failure with detailed context.
        """
        try:
            self.stage_user_changes(user)
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            self._notify_error("Git Stage Failed", f"Could not stage changes: {error_msg}")
            raise GitError(f"Staging failed: {error_msg}", "stage_user_changes", e.stderr, e.returncode)
        
        # Try to commit. Return code 1 with "nothing to commit" is OK.
        try:
            self.commit(f'Update by {user}')
        except subprocess.CalledProcessError as e:
            # Check if this is the expected "nothing to commit" case
            if e.returncode == 1 and e.stdout and 'nothing to commit' in e.stdout.lower():
                # This is fine - no changes to commit, but we still want to push unpushed commits
                pass
            elif e.returncode == 1 and e.stderr and 'nothing to commit' in e.stderr.lower():
                # Same check for stderr
                pass
            else:
                # Real commit failure
                error_msg = e.stderr.strip() if e.stderr else e.stdout.strip() if e.stdout else str(e)
                self._notify_error("Git Commit Failed", f"Could not commit: {error_msg}")
                raise GitError(f"Commit failed: {error_msg}", "commit", e.stderr, e.returncode)

        # Pull and Push MUST succeed. If they fail, GitError is raised with notification.
        self.pull_rebase()
        self.push()
        return True

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
