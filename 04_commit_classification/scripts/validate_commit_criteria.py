import csv
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error

# UTF-8 encoding configuration for Windows console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from pathlib import Path

# Load .env if available
env_candidates = [
    Path(".env"),
    Path(__file__).resolve().parent / ".env",
    Path(__file__).resolve().parents[2] / ".env"
]
for p in env_candidates:
    if p.exists():
        with open(p, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ[k.strip()] = v.strip().strip('"').strip("'")
        break

# Heuristic definitions
INTERACTIVE_AI_LOGINS = [
    r"cursor", r"copilot", r"devin", r"claude", r"jules", r"sweep", r"codeium", r"qodo", r"clawsweeper"
]

BOT_LOGINS = [
    r"\[bot\]$", r"bot$", r"^dependabot", r"^renovate", r"^github-actions", r"^mergify"
]

INTERACTIVE_AI_EMAILS = [
    (r"noreply@anthropic\.com", "Anthropic AI Email"),
    (r"noreply@openai\.com", "OpenAI AI Email"),
    (r"copilot", "Copilot Email Keyword"),
    (r"cursor", "Cursor Email Keyword"),
    (r"devin", "Devin Email Keyword"),
    (r"sweep", "Sweep Email Keyword"),
    (r"claude", "Claude Email Keyword"),
    (r"jules", "Jules Email Keyword"),
    (r"codeium", "Codeium Email Keyword"),
    (r"qodo", "Qodo Email Keyword"),
    (r"clawsweeper", "ClawSweeper Email Keyword")
]

BOT_EMAILS = [
    (r"\[bot\]@users\.noreply\.github\.com", "GitHub Bot User Email"),
    (r"github-actions", "GitHub Actions Email"),
    (r"dependabot", "Dependabot Email"),
    (r"renovate", "Renovate Email")
]

INTERACTIVE_AI_NAMES = [
    (r"Cursor\s*Agent", "Cursor Agent Name"),
    (r"\bCursor\b", "Cursor Name"),
    (r"GitHub\s*Copilot", "GitHub Copilot Name"),
    (r"\bCopilot\b", "Copilot Name"),
    (r"\bClaude\b", "Claude AI Name"),
    (r"\bJules\b", "Jules AI Name"),
    (r"\bDevin\b", "Devin AI Name"),
    (r"\bSweep\b", "Sweep AI Name"),
    (r"ClawSweeper", "ClawSweeper Name"),
    (r"\bCodeium\b", "Codeium AI Name"),
    (r"\bQodo\b", "Qodo AI Name")
]

BOT_NAMES = [
    (r"\[bot\]", "[bot] in Name"),
    (r"\bBot\b", "Bot in Name")
]

INTERACTIVE_AI_TRAILERS = [
    (r"Co-authored-by:.*(?:cursor|copilot|claude|devin|jules|sweep|codeium|qodo)", "Co-authored-by AI Trailer"),
    (r"Generated-by:\s*(?:Cursor|Copilot|Claude|Devin|Jules|Sweep|AI)", "Generated-by AI Trailer"),
    (r"AI-generated", "AI-generated keyword in commit message"),
    (r"AI-assisted", "AI-assisted keyword in commit message"),
    (r"Assisted-by:\s*(?:Cursor|Copilot|Claude|Devin|Jules|AI)", "Assisted-by AI Trailer"),
    (r"Co-authored-by:\s*Claude", "Co-authored-by Claude"),
    (r"Co-authored-by:\s*Cursor", "Co-authored-by Cursor"),
    (r"Co-authored-by:\s*Copilot", "Co-authored-by Copilot"),
    (r"Co-authored-by:\s*Devin", "Co-authored-by Devin")
]

BOT_TRAILERS = [
    (r"Co-authored-by:.*<.*\[bot\]@users\.noreply\.github\.com>", "Co-authored-by Bot Email Trailer"),
    (r"Co-authored-by:.*\[bot\]", "Co-authored-by Bot Trailer")
]

# Suggested Additional Signals: PR linkage, Checkboxes & PR Labels
PR_SUGGESTED_PATTERNS = [
    (r"\[x\]\s*(?:Generated|Assisted)\s+with\s+(?:Claude|Cursor|Copilot|Devin|AI)", "PR Template Checkbox Attribution"),
    (r"PR\s+Attribution:\s*(?:Claude|Cursor|Copilot|Devin)", "PR Body Attribution Header"),
    (r"ai-generated", "PR Label Signature: ai-generated"),
    (r"claude-code", "PR Label Signature: claude-code")
]

def check_commit_signatures(commit_data):
    sha = commit_data.get("sha", "")
    commit_obj = commit_data.get("commit", {})
    git_author = commit_obj.get("author", {}) or {}
    git_committer = commit_obj.get("committer", {}) or {}
    message = commit_obj.get("message", "") or ""
    
    gh_author = commit_data.get("author") or {}
    gh_committer = commit_data.get("committer") or {}
    
    author_login = gh_author.get("login", "")
    committer_login = gh_committer.get("login", "")
    author_name = git_author.get("name", "")
    committer_name = git_committer.get("name", "")
    author_email = git_author.get("email", "")
    committer_email = git_committer.get("email", "")

    ai_matches = {
        "1_actor_logins": [],
        "2_author_emails": [],
        "3_author_names": [],
        "4_commit_trailers": [],
        "5_suggested_pr_signals": []
    }
    bot_matches = {
        "1_actor_logins": [],
        "2_author_emails": [],
        "3_author_names": [],
        "4_commit_trailers": [],
        "5_suggested_pr_signals": []
    }

    # 1. Logins
    logins = [("author_login", author_login), ("committer_login", committer_login)]
    for role, login in logins:
        if not login:
            continue
        for pat in INTERACTIVE_AI_LOGINS:
            if re.search(pat, login, re.IGNORECASE):
                ai_matches["1_actor_logins"].append(f"{role}: {login} (AI regex '{pat}')")
        for pat in BOT_LOGINS:
            if re.search(pat, login, re.IGNORECASE):
                bot_matches["1_actor_logins"].append(f"{role}: {login} (Bot regex '{pat}')")

    # 2. Emails
    emails = [("author_email", author_email), ("committer_email", committer_email)]
    for role, email in emails:
        if not email:
            continue
        for pat, label in INTERACTIVE_AI_EMAILS:
            if re.search(pat, email, re.IGNORECASE):
                ai_matches["2_author_emails"].append(f"{role}: {email} ({label})")
        for pat, label in BOT_EMAILS:
            if re.search(pat, email, re.IGNORECASE):
                bot_matches["2_author_emails"].append(f"{role}: {email} ({label})")

    # 3. Names
    names = [("author_name", author_name), ("committer_name", committer_name)]
    for role, name in names:
        if not name:
            continue
        for pat, label in INTERACTIVE_AI_NAMES:
            if re.search(pat, name, re.IGNORECASE):
                ai_matches["3_author_names"].append(f"{role}: '{name}' ({label})")
        for pat, label in BOT_NAMES:
            if re.search(pat, name, re.IGNORECASE):
                bot_matches["3_author_names"].append(f"{role}: '{name}' ({label})")

    # 4. Message & Trailers
    for pat, label in INTERACTIVE_AI_TRAILERS:
        if re.search(pat, message, re.IGNORECASE):
            ai_matches["4_commit_trailers"].append(f"Commit message ({label})")
    for pat, label in BOT_TRAILERS:
        if re.search(pat, message, re.IGNORECASE):
            bot_matches["4_commit_trailers"].append(f"Commit message ({label})")

    # 5. Suggested PR Signals (Parsed from commit body / PR references)
    for pat, label in PR_SUGGESTED_PATTERNS:
        if re.search(pat, message, re.IGNORECASE):
            ai_matches["5_suggested_pr_signals"].append(f"PR/Body ({label})")

    active_ai = {k: v for k, v in ai_matches.items() if v}
    active_bot = {k: v for k, v in bot_matches.items() if v}

    if active_ai:
        classification = "INTERACTIVE_AI_COAUTHORED"
    elif active_bot:
        classification = "AUTONOMOUS_BOT"
    else:
        classification = "HUMAN_ONLY"

    return classification, active_ai if active_ai else active_bot

def get_target_repos(csv_path="Repos_Final_Sample.csv"):
    candidates = [
        Path(csv_path),
        Path(__file__).resolve().parents[2] / "02_repo_sampling" / "data" / csv_path,
        Path("02_repo_sampling/data") / csv_path,
        Path("../data") / csv_path,
    ]
    resolved_path = None
    for c in candidates:
        if c.exists():
            resolved_path = c
            break

    if not resolved_path:
        print(f"Error: {csv_path} not found.")
        return []

    repos = []
    with open(resolved_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = row.get("Repo_URL", "").strip()
            name = row.get("Repo_Name", "").strip() or row.get("\ufeffRepo_Name", "").strip()
            if url:
                parts = url.rstrip("/").split("/")
                if len(parts) >= 2:
                    owner_repo = f"{parts[-2]}/{parts[-1]}"
                    repos.append((name, owner_repo, url))
            elif name and "/" in name:
                repos.append((name, name, f"https://github.com/{name}"))
    return repos

def fetch_json_with_retry(url, headers, max_retries=3):
    for attempt in range(max_retries):
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req) as resp:
                rate_limit_rem = resp.headers.get("X-RateLimit-Remaining")
                if rate_limit_rem and int(rate_limit_rem) < 20:
                    print(f"  Warning: RateLimit Low ({rate_limit_rem} remaining). Pacing 1s.")
                    time.sleep(1)
                data = json.loads(resp.read().decode("utf-8"))
                return data, None
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                print(f"  Rate limit / HTTP {e.code} hit. Slowing down...")
                time.sleep(5)
            else:
                return None, e
        except Exception as e:
            time.sleep(2)
    return None, "Max retries exceeded"

def main():
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    headers = {
        "User-Agent": "Commit-Classification-Validator/1.0",
        "Accept": "application/vnd.github.v3+json"
    }
    if token:
        headers["Authorization"] = f"token {token}"
        print("Using GitHub Token authentication.")
    else:
        print("No GITHUB_TOKEN set. Operating unauthenticated.")

    repos = get_target_repos()
    print(f"Total target repositories loaded from CSV: {len(repos)}")
    
    max_repos_to_scan = 50
    commits_per_repo = 100
    
    total_scanned = 0
    classification_counts = {
        "INTERACTIVE_AI_COAUTHORED": 0,
        "AUTONOMOUS_BOT": 0,
        "HUMAN_ONLY": 0
    }
    
    matched_ai_commits = []
    matched_bot_commits = []
    human_sample_commits = []

    print("=" * 80)
    print("STARTING EMPIRICAL SCAN WITH SUGGESTED CRITERIA & FULL COMMIT LINKS")
    print("=" * 80)

    for idx, (repo_alias, owner_repo, repo_url) in enumerate(repos[:max_repos_to_scan], 1):
        url = f"https://api.github.com/repos/{owner_repo}/commits?per_page={commits_per_repo}"
        print(f"[{idx}/{max_repos_to_scan}] Fetching commits for {owner_repo}...")
        
        commits, err = fetch_json_with_retry(url, headers)
        if err or not commits:
            print(f"  Skipping {owner_repo} due to error: {err}")
            continue

        for c in commits:
            total_scanned += 1
            sha = c.get("sha", "")
            short_sha = sha[:7]
            full_commit_link = f"https://github.com/{owner_repo}/commit/{sha}"
            
            label, details = check_commit_signatures(c)
            classification_counts[label] += 1

            commit_obj = c.get("commit", {})
            git_author = commit_obj.get("author", {}) or {}
            msg = (commit_obj.get("message", "") or "").strip()
            first_line = msg.split("\n")[0] if msg else ""
            gh_author = c.get("author") or {}

            info = {
                "repo": owner_repo,
                "sha": sha,
                "short_sha": short_sha,
                "commit_link": full_commit_link,
                "author_name": git_author.get("name", "N/A"),
                "author_login": gh_author.get("login", "N/A"),
                "author_email": git_author.get("email", "N/A"),
                "snippet": first_line,
                "signatures": details,
                "classification": label
            }

            if label == "INTERACTIVE_AI_COAUTHORED":
                matched_ai_commits.append(info)
            elif label == "AUTONOMOUS_BOT":
                matched_bot_commits.append(info)
            elif len(human_sample_commits) < 20:
                human_sample_commits.append(info)

        time.sleep(0.1)

    print("\n" + "=" * 80)
    print("EMPIRICAL CLASSIFICATION SUMMARY")
    print("=" * 80)
    print(f"Total Repositories Scanned                   : {min(idx, max_repos_to_scan)}")
    print(f"Total Commits Evaluated                      : {total_scanned:,}")
    print(f"1. Interactive AI-Co-Authored Commits        : {classification_counts['INTERACTIVE_AI_COAUTHORED']:,} ({ (classification_counts['INTERACTIVE_AI_COAUTHORED']/total_scanned*100) if total_scanned else 0:.2f}%)")
    print(f"2. Autonomous DevOps / Dependency Bots       : {classification_counts['AUTONOMOUS_BOT']:,} ({ (classification_counts['AUTONOMOUS_BOT']/total_scanned*100) if total_scanned else 0:.2f}%)")
    print(f"3. Pure Human-Only Commits                   : {classification_counts['HUMAN_ONLY']:,} ({ (classification_counts['HUMAN_ONLY']/total_scanned*100) if total_scanned else 0:.2f}%)")
    print("=" * 80)

    # Save to JSON dataset file
    output_dir = Path(__file__).resolve().parent.parent / "data"
    if not output_dir.exists():
        output_dir = Path(".")
    output_filepath = output_dir / "multi_repo_commit_validation.json"
    with open(output_filepath, "w", encoding="utf-8") as f:
        json.dump({
            "scanned_repos_count": min(idx, max_repos_to_scan),
            "total_scanned_commits": total_scanned,
            "classification_counts": classification_counts,
            "ai_coauthored_commits": matched_ai_commits,
            "autonomous_bot_commits": matched_bot_commits,
            "human_sample_commits": human_sample_commits
        }, f, indent=2)
    print(f"\nSaved empirical dataset results with full commit links to '{output_filepath}'")

if __name__ == "__main__":
    main()
