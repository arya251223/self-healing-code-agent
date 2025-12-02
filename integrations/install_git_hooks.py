"""Install git hooks for automatic healing (Windows + Linux compatible)"""

import os
import stat
import shutil

def install_hooks(repo_path: str = "."):
    """Install git hooks with Windows support"""
    
    hooks_dir = os.path.join(repo_path, ".git", "hooks")

    if not os.path.exists(hooks_dir):
        print("⚠️ Not a git repository")
        return False

    # Path for pre-commit hook
    pre_commit_path = os.path.join(hooks_dir, "pre-commit")

    # If pre-commit exists as a DIRECTORY → delete it
    if os.path.isdir(pre_commit_path):
        print("⚠️ 'pre-commit' exists as a folder → deleting wrong folder...")
        shutil.rmtree(pre_commit_path, ignore_errors=True)

    # If pre-commit file exists but read-only → unlock
    if os.path.exists(pre_commit_path):
        os.chmod(pre_commit_path, stat.S_IWRITE)

    # Python hook content (Linux/macOS)
    hook_content_unix = """#!/usr/bin/env python3
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from integrations.git_auto_healer import run_pre_commit_scan
run_pre_commit_scan()
"""

    # Python hook for Windows (Git Bash & CMD)
    hook_content_win = """@echo off
python "%~dp0\\..\\..\\integrations\\git_auto_healer.py" precommit
"""

    # Write cross-platform hooks
    with open(pre_commit_path, "w", newline="\n") as f:
        f.write(hook_content_unix)

    # Make executable (Linux/macOS)
    try:
        st = os.stat(pre_commit_path)
        os.chmod(pre_commit_path, st.st_mode | stat.S_IEXEC)
    except:
        pass

    # Create Windows-compatible hook (.cmd)
    pre_commit_cmd = os.path.join(hooks_dir, "pre-commit.cmd")
    with open(pre_commit_cmd, "w", newline="\r\n") as f:
        f.write(hook_content_win)

    print("✓ Git hooks installed successfully (Windows + Linux)")
    return True


if __name__ == "__main__":
    install_hooks()
