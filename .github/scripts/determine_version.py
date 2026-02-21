
import os
import sys
import argparse
import re

_SUBJECT_RE = re.compile(r'^(\w+)(\([^)]+\))?(!)?:')

def get_current_version(version_file):
    """Reads the current version from the specified file, defaulting to 0.1.0."""
    try:
        with open(version_file, "r") as f:
            return f.read().strip()
    except FileNotFoundError:
        return "0.1.0"

def get_version_bump_from_commits(commits: str) -> str:
    """Determines version bump level from conventional commit messages."""
    level = 0  # 0=PATCH, 1=MINOR, 2=MAJOR
    for line in commits.splitlines():
        line = line.strip()
        if not line:
            continue
        # Check for BREAKING CHANGE footer in commit body
        if line.startswith("BREAKING CHANGE:") or line.startswith("BREAKING-CHANGE:"):
            level = 2
            break  # MAJOR is maximum; no need to continue
        m = _SUBJECT_RE.match(line)
        if m:
            commit_type = m.group(1).lower()
            has_bang = m.group(3) == '!'
            if has_bang:
                level = 2
                break  # MAJOR is maximum; no need to continue
            if commit_type == 'feat':
                level = max(level, 1)
            # fix:, ci:, chore:, etc. → PATCH (level 0), already covered by default
    return ['PATCH', 'MINOR', 'MAJOR'][level]

def get_next_version(current_version, bump_level):
    """Calculates the next version based on the bump level."""
    major, minor, patch = map(int, current_version.split("."))
    if bump_level == "MAJOR":
        major += 1
        minor = 0
        patch = 0
    elif bump_level == "MINOR":
        minor += 1
        patch = 0
    else:  # PATCH
        patch += 1
    return f"{major}.{minor}.{patch}"

def get_version_bump_from_gemini(api_key, commits):
    """Determines the version bump using the Gemini API."""
    import google.generativeai as genai
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')

        prompt = f"""
        You are an expert in Semantic Versioning and Conventional Commits.
        Analyze the following commit messages and determine the appropriate version bump.
        The possible bumps are MAJOR, MINOR, or PATCH.

        - A 'feat:' prefix indicates a MINOR bump.
        - A 'fix:' prefix indicates a PATCH bump.
        - The presence of 'BREAKING CHANGE:' in the commit body indicates a MAJOR bump.
        - If there are multiple commits, choose the highest bump level. For example, if there is one 'feat' and one 'fix', the bump should be MINOR. If there is a 'BREAKING CHANGE', it should always be MAJOR.
        - Respond with only one word: MAJOR, MINOR, or PATCH.

        Here are the commit messages:
        {commits}
        """

        response = model.generate_content(prompt)
        bump = response.text.strip().upper()
        if bump in ["MAJOR", "MINOR", "PATCH"]:
            return bump
        else:
            # If Gemini returns something unexpected, default to PATCH
            return "PATCH"
    except Exception as e:
        print(f"Error calling Gemini API: {e}. Defaulting to PATCH.", file=sys.stderr)
        return "PATCH"

def main():
    """Entry point: determines the next version based on commit messages."""
    parser = argparse.ArgumentParser(description="Determine the next version based on commit messages.")
    parser.add_argument("--commits", required=True, help="A string containing all commit messages.")
    parser.add_argument("--version-file", default="version.txt", help="The file containing the current version.")
    parser.add_argument("--use-ai", action="store_true", default=False, help="Use Gemini AI for version determination.")
    args = parser.parse_args()

    current_version = get_current_version(args.version_file)

    if args.use_ai:
        print("🤖 Using Gemini AI for version determination...")
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            print("Error: GEMINI_API_KEY environment variable not set.", file=sys.stderr)
            sys.exit(1)
        bump_level = get_version_bump_from_gemini(api_key, args.commits)
    else:
        print("🔍 Determining next version from conventional commits...")
        bump_level = get_version_bump_from_commits(args.commits)

    next_version = get_next_version(current_version, bump_level)
    print(next_version)

if __name__ == "__main__":
    main()
