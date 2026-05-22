import os
import argparse
import re
import sys

def validate_skill(path):
    skill_dir = os.path.basename(os.path.normpath(path))
    skill_md_path = os.path.join(path, 'SKILL.md')
    errors = []
    warnings = []

    print(f"Validating skill: {skill_dir}...")

    # 1. CRITICAL: Identity & Naming (Strict)
    if not re.match(r'^[a-z0-9][a-z0-9-]*[a-z0-9]$', skill_dir):
        errors.append("Directory name violates regex (lowercase/hyphens only).")

    # 2. CRITICAL: The Entry Point (Strict)
    if not os.path.exists(skill_md_path):
        errors.append("Missing SKILL.md (The mandatory entry point).")
    
    # 3. CRITICAL: Metadata Consistency (Strict)
    if os.path.exists(skill_md_path):
        with open(skill_md_path, 'r') as f:
            content = f.read()

        # Only inspect the YAML frontmatter block (between the first two '---'
        # lines), so example frontmatter in the body can't cause false matches.
        fm_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if not fm_match:
            errors.append("Missing YAML frontmatter block (--- ... ---).")
            frontmatter = ""
        else:
            frontmatter = fm_match.group(1)

        name_match = re.search(r'^name:\s*(.+)$', frontmatter, re.MULTILINE)
        if not name_match:
            errors.append("YAML frontmatter missing 'name' field.")
        elif name_match.group(1).strip() != skill_dir:
            errors.append(f"YAML name '{name_match.group(1).strip()}' mismatches directory '{skill_dir}'.")

        if not re.search(r'^description:\s*(.+)$', frontmatter, re.MULTILINE):
            errors.append("YAML frontmatter missing 'description' field.")

        # Repo convention: every skill declares a top-level 'license' (an SPDX
        # id) and a 'metadata.source' (the upstream it was vendored/adapted
        # from). Advisory — warn rather than fail.
        if not re.search(r'^license:\s*(.+)$', frontmatter, re.MULTILINE):
            warnings.append("Frontmatter missing top-level 'license' (SPDX id, e.g. Apache-2.0). Required by repo convention.")
        if not re.search(r'^\s+source:\s*\S', frontmatter, re.MULTILINE):
            warnings.append("Frontmatter missing 'metadata.source' (upstream URL). Required by repo convention.")

    # 4. ADVISORY: Progressive Disclosure (Flexible)
    # We check if they exist, but we do not fail if they don't.
    has_refs = os.path.isdir(os.path.join(path, 'references'))
    has_scripts = os.path.isdir(os.path.join(path, 'scripts'))

    if not has_refs:
        warnings.append("No 'references/' directory found. (Acceptable for simple skills).")
    
    if not has_scripts:
        warnings.append("No 'scripts/' directory found. (Acceptable for pure-prompt skills).")

    # Final Report
    if errors:
        print("\n[FAIL] Critical Violations:")
        for e in errors: print(f"  ❌ {e}")
        sys.exit(1)
    else:
        print("\n[PASS] Skill is valid.")
        if warnings:
            print("[INFO] Architectural Notes:")
            for w in warnings: print(f"  ℹ️  {w}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Validate an Agent Skill.')
    parser.add_argument('--path', required=True, help='Skill root path')
    args = parser.parse_args()
    validate_skill(args.path)