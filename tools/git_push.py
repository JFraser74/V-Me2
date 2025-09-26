"""Safe git push helper for CI or in-app agent.

This helper is intentionally simple and requires the following env vars when used non-interactively:
- GITHUB_ACTOR
- GITHUB_PAT

Usage (local interactive):
  python tools/git_push.py --remote "https://github.com/owner/repo.git" --branch main

The script prompts before pushing when not all env vars are present.
"""
import os
import argparse
import subprocess
import sys

def run(cmd):
    print("$", " ".join(cmd))
    subprocess.check_call(cmd)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--remote', required=True)
    parser.add_argument('--branch', default='main')
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()

    gh_actor = os.environ.get('GITHUB_ACTOR')
    gh_pat = os.environ.get('GITHUB_PAT')

    if not gh_actor or not gh_pat:
        print('GITHUB_ACTOR or GITHUB_PAT not set. Please set them or run interactively.')
        resp = input('Proceed with interactive push? [y/N] ').strip().lower()
        if resp != 'y':
            sys.exit(1)
        run(['git', 'remote', 'add', 'temp-origin', args.remote])
        run(['git', 'push', 'temp-origin', f'HEAD:{args.branch}'])
        run(['git', 'remote', 'remove', 'temp-origin'])
        return

    # Construct authenticated remote
    if args.remote.startswith('https://'):
        proto_removed = args.remote[len('https://'):]
        authed = f'https://{gh_actor}:{gh_pat}@{proto_removed}'
    else:
        authed = args.remote

    run(['git', 'push', authed, f'HEAD:{args.branch}'] + (['--force'] if args.force else []))

if __name__ == '__main__':
    main()
