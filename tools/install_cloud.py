#!/usr/bin/env python3
"""Link the canonical organization checkout into Claude's cloud configuration."""
import argparse
import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).absolute().parent.parent
MARKER = '<!-- engineer-org: reference only -->'


def install(root, config):
    root = Path(root).resolve()
    config = Path(os.path.abspath(config))
    if any(p.is_symlink() for p in [config, *config.parents]):
        raise ValueError('Refusing a symlink in configuration directory')
    roles = json.loads((root / '組織/役割/定義.json').read_text())
    links = {config / 'engineer-org': root}
    for role in roles:
        name = role['name']
        if not name.startswith('org-') or '/' in name or '\\' in name:
            raise ValueError('Invalid role name')
        links[config / 'agents' / (name + '.md')] = root / '.claude/agents' / (name + '.md')
    skills = sorted((root / '.claude/skills').glob('org-*/SKILL.md'))
    for definition in skills:
        name = definition.parent.name
        if not re.fullmatch(r'org-[a-z0-9]+(?:-[a-z0-9]+)*', name):
            raise ValueError('Invalid skill name')
        links[config / 'skills' / name] = definition.parent
    # Only pointers are written here. Rule, role and skill bodies stay in Git.
    entry = config / 'CLAUDE.md'
    content = (MARKER + '\n@' + str(root / 'AGENTS.md') + '\n\n'
               + '組織の起点は `' + str(root) + '`。組織の指示にある相対パスはこの起点から解決する。\n')
    if entry.is_symlink() or (entry.exists() and (not entry.is_file() or entry.read_text() != content)):
        raise ValueError('Existing CLAUDE.md differs; keep it and resolve the reference explicitly')
    # Preflight every target before writing anything; never replace personal settings.
    for target, source in links.items():
        if not source.exists():
            raise ValueError('Canonical source missing: ' + str(source))
        if any(p.is_symlink() or (p.exists() and not p.is_dir()) for p in target.parents):
            raise ValueError('Invalid parent of ' + str(target))
        if target.is_symlink():
            if target.resolve() != source.resolve():
                raise ValueError('Existing link differs: ' + str(target))
        elif target.exists():
            raise ValueError('Existing configuration differs: ' + str(target))
    # Retire only references previously installed from this checkout.
    removals = []
    for relative in ('agents/org-support.md', 'skills/org-fable-consult'):
        retired = config / relative
        if not (retired.is_symlink() or retired.exists()):
            continue
        owned = {(root / '.claude' / relative).resolve(),
                 (root / '共通/.claude' / relative).resolve()}
        if any(p.is_symlink() for p in retired.parents):
            raise ValueError('Invalid parent of retired role: ' + str(retired))
        if not retired.is_symlink() or retired.resolve() not in owned:
            raise ValueError('Existing retired configuration differs; preserve and resolve explicitly: ' + str(retired))
        removals.append(retired)
    for retired in removals:
        retired.unlink()
    for target, source in links.items():
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.is_symlink():
            target.symlink_to(source, target_is_directory=source.is_dir())
    if not entry.exists():
        entry.write_text(content)
    print('engineer-org: canonical checkout referenced; ' + str(len(roles)) + ' roles and ' + str(len(skills)) + ' skills linked')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--claude-dir', type=Path, default=Path.home() / '.claude')
    args = parser.parse_args()
    try:
        install(ROOT, args.claude_dir)
    except (ValueError, OSError) as exc:
        parser.exit(1, str(exc) + '\n')
