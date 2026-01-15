import subprocess
from src.git_manager import GitManager
from unittest.mock import patch


def test_pull_rebase_calls_git_pull_rebase():
    with patch('src.git_manager.subprocess.run') as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(
            args=['git', 'pull', '--rebase'], returncode=0, stdout='pulled', stderr=''
        )

        gm = GitManager()
        result = gm.pull_rebase()

        # Ensure subprocess.run was called once with the expected arguments
        mock_run.assert_called_once()
        called_args, called_kwargs = mock_run.call_args
        # First positional argument is the command list
        assert called_args[0] == ['git', 'pull', '--rebase']
        # Ensure we passed through the repo path (None by default) and standard kwargs
        assert called_kwargs.get('cwd', None) is None
        assert called_kwargs.get('check', False) is True
        assert 'stdout' in called_kwargs and 'stderr' in called_kwargs and 'text' in called_kwargs

        # Ensure the returned value is the CompletedProcess we configured
        assert isinstance(result, subprocess.CompletedProcess)
        assert result.stdout == 'pulled'


def test_push_changes_calls_add_commit_push_and_with_message():
    with patch('src.git_manager.subprocess.run') as mock_run:
        # Prepare three CompletedProcess results for add, commit, push
        mock_run.side_effect = [
            subprocess.CompletedProcess(args=['git', 'add', '.'], returncode=0, stdout='', stderr=''),
            subprocess.CompletedProcess(args=['git', 'commit', '-m', 'Update by Alex'], returncode=0, stdout='', stderr=''),
            subprocess.CompletedProcess(args=['git', 'push'], returncode=0, stdout='', stderr=''),
        ]

        repo_path = '/path/to/repo'
        gm = GitManager(repo_path=repo_path)
        results = gm.push_changes('Alex')

        # Ensure we got three results back
        assert len(results) == 3

        # Ensure subprocess.run was called three times with the correct commands in order
        assert mock_run.call_count == 3
        call_list = mock_run.call_args_list

        # First call: git add .
        args0, kwargs0 = call_list[0]
        assert args0[0] == ['git', 'add', '.']
        assert kwargs0['cwd'] == repo_path
        assert kwargs0['check'] is True

        # Second call: git commit -m "Update by Alex"
        args1, kwargs1 = call_list[1]
        assert args1[0] == ['git', 'commit', '-m', 'Update by Alex']
        assert kwargs1['cwd'] == repo_path
        assert kwargs1['check'] is True

        # Third call: git push
        args2, kwargs2 = call_list[2]
        assert args2[0] == ['git', 'push']
        assert kwargs2['cwd'] == repo_path
        assert kwargs2['check'] is True
