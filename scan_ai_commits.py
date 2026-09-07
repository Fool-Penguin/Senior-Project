import json
import os
import re
import sys
import time
import urllib.request
import urllib.error

# Ensure stdout handles UTF-8 characters on Windows console without crashing
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Automatically load .env if present
env_path = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(env_path):
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip('"').strip("'")

REPO_OWNER = "openclaw"
REPO_NAME = "openclaw"
MAX_PAGES = 100  # 100 pages * 100 commits/page = 10,000 commits sample
PER_PAGE = 100

# Patterns based on "Debt Behind the AI Boom: A Large-Scale Empirical Study of AI-Generated Code in the Wild"
BOT_LOGIN_PATTERNS = [
    r"\[bot\]$",
    r"bot$",
    r"^dependabot",
    r"^renovate",
    r"^github-actions",
    r"cursor",
    r"copilot",
    r"devin",
    r"claude",
    r"jules",
    r"sweep",
    r"codeium",
    r"qodo"
]

EMAIL_PATTERNS = [
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
    (r"\[bot\]@users\.noreply\.github\.com", "GitHub Bot User Email"),
    (r"github-actions", "GitHub Actions Email"),
    (r"dependabot", "Dependabot Email"),
    (r"renovate", "Renovate Email")
]

NAME_PATTERNS = [
    (r"Cursor\s*Agent", "Cursor Agent Name"),
    (r"Cursor", "Cursor Name"),
    (r"GitHub\s*Copilot", "GitHub Copilot Name"),
    (r"Copilot", "Copilot Name"),
    (r"Claude", "Claude AI Name"),
    (r"Jules", "Jules AI Name"),
    (r"Devin", "Devin AI Name"),
    (r"Sweep", "Sweep AI Name"),
    (r"Codeium", "Codeium AI Name"),
    (r"Qodo", "Qodo AI Name"),
    (r"\[bot\]", "[bot] in Name"),
    (r"\bBot\b", "Bot in Name")
]

TRAILER_PATTERNS = [
    (r"Co-authored-by:.*(?:cursor|copilot|claude|devin|jules|sweep|codeium|qodo|bot)", "Co-authored-by AI/Bot Trailer"),
    (r"Co-authored-by:\s*(?:Cursor|Copilot|Claude|Devin|Jules|Sweep|Codeium|Qodo)", "Co-authored-by AI Trailer"),
    (r"Generated-by:\s*(?:Cursor|Copilot|Claude|Devin|Jules|Sweep|AI)", "Generated-by AI Trailer"),
    (r"AI-generated", "AI-generated keyword in commit message"),
    (r"Assisted-by:\s*(?:Cursor|Copilot|Claude|Devin|Jules|AI)", "Assisted-by AI Trailer"),
    (r"Co-authored-by:.*<.*\[bot\]@users\.noreply\.github\.com>", "Co-authored-by Bot Email Trailer"),
    (r"\bCursor\b", "Cursor mentioned in commit message"),
    (r"\bCopilot\b", "Copilot mentioned in commit message"),
    (r"\bClaude\b", "Claude mentioned in commit message"),
    (r"\bDevin\b", "Devin mentioned in commit message")
]

def check_heuristics(commit_data):
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
    
    matches = {
        "1_actor_logins": [],
        "2_author_emails": [],
        "3_author_names": [],
        "4_commit_trailers": []
    }
    
    # 1. Actor Logins
    logins_to_check = [("author_login", author_login), ("committer_login", committer_login)]
    for role, login in logins_to_check:
        if not login:
            continue
        if "[bot]" in login.lower():
            matches["1_actor_logins"].append(f"{role}: {login} (contains '[bot]')")
        else:
            for pat in BOT_LOGIN_PATTERNS:
                if re.search(pat, login, re.IGNORECASE):
                    matches["1_actor_logins"].append(f"{role}: {login} (matches regex '{pat}')")
                    break
                    
    # 2. Author Emails
    emails_to_check = [("author_email", author_email), ("committer_email", committer_email)]
    for role, email in emails_to_check:
        if not email:
            continue
        for pat, label in EMAIL_PATTERNS:
            if re.search(pat, email, re.IGNORECASE):
                matches["2_author_emails"].append(f"{role}: {email} ({label})")

    # 3. Author Names
    names_to_check = [("author_name", author_name), ("committer_name", committer_name)]
    for role, name in names_to_check:
        if not name:
            continue
        for pat, label in NAME_PATTERNS:
            if re.search(pat, name, re.IGNORECASE):
                matches["3_author_names"].append(f"{role}: '{name}' ({label})")

    # 4. Commit Messages / Trailers
    for pat, label in TRAILER_PATTERNS:
        if re.search(pat, message, re.IGNORECASE):
            matches["4_commit_trailers"].append(f"Commit message ({label})")

    # Filter out empty categories
    active_matches = {k: v for k, v in matches.items() if v}
    return active_matches

def fetch_commits(owner, repo, max_pages=100, per_page=100):
    all_commits = []
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    
    headers = {
        "User-Agent": "AI-Code-Debt-Scanner/1.0",
        "Accept": "application/vnd.github.v3+json"
    }
    if token:
        headers["Authorization"] = f"token {token}"
        print(f"Using GitHub Token authentication.")
    else:
        print(f"No GITHUB_TOKEN found. Operating in unauthenticated REST API mode.")

    for page in range(1, max_pages + 1):
        url = f"https://api.github.com/repos/{owner}/{repo}/commits?per_page={per_page}&page={page}"
        if page % 5 == 0 or page == 1 or page == max_pages:
            print(f"Fetching page {page}/{max_pages} from GitHub API...")
        
        req = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(req) as resp:
                rate_limit_rem = resp.headers.get("X-RateLimit-Remaining")
                if rate_limit_rem is not None and int(rate_limit_rem) < 50:
                    print(f"  Warning: RateLimit Low ({rate_limit_rem} remaining). Pausing brief period.")
                    time.sleep(2)
                
                data = json.loads(resp.read().decode("utf-8"))
                if not data:
                    print(f"Page {page} returned no commits. Reached end of commit history.")
                    break
                all_commits.extend(data)
                
                # Small pause if unauthenticated
                if not token:
                    time.sleep(1)
        except urllib.error.HTTPError as e:
            print(f"HTTP Error {e.code}: {e.reason} while fetching page {page}")
            if e.code == 403 and "rate limit" in str(e.reason).lower():
                print("Rate limit reached. Stopping pagination.")
            break
        except Exception as e:
            print(f"Error fetching page {page}: {e}")
            break

    return all_commits

def main():
    print("=" * 80)
    print(f"Scanning remote repository: {REPO_OWNER}/{REPO_NAME} via GitHub REST API")
    print(f"Target Sample Size: {MAX_PAGES * PER_PAGE:,} commits ({MAX_PAGES} pages)")
    print("Methodology: 'Debt Behind the AI Boom: A Large-Scale Empirical Study of AI-Generated Code in the Wild'")
    print("=" * 80)
    
    commits = fetch_commits(REPO_OWNER, REPO_NAME, max_pages=MAX_PAGES, per_page=PER_PAGE)
    total_scanned = len(commits)
    print(f"\nTotal commits fetched and scanned: {total_scanned:,}\n")

    results = []
    category_counts = {
        "1_actor_logins": 0,
        "2_author_emails": 0,
        "3_author_names": 0,
        "4_commit_trailers": 0
    }
    
    matched_commits_count = 0

    print("-" * 80)
    print("MATCHED COMMITS WITH AI / BOT SIGNATURES")
    print("-" * 80)

    for idx, c in enumerate(commits, 1):
        heuristics = check_heuristics(c)
        if heuristics:
            matched_commits_count += 1
            sha = c.get("sha", "")
            short_sha = sha[:8]
            
            commit_obj = c.get("commit", {})
            git_author = commit_obj.get("author", {}) or {}
            message = (commit_obj.get("message", "") or "").strip()
            first_line = message.split("\n")[0] if message else ""
            
            gh_author = c.get("author") or {}
            author_login = gh_author.get("login", "N/A")
            author_name = git_author.get("name", "N/A")
            author_email = git_author.get("email", "N/A")

            # Track category totals
            for cat in heuristics.keys():
                category_counts[cat] += 1

            matched_info = {
                "index": idx,
                "sha": sha,
                "short_sha": short_sha,
                "author_name": author_name,
                "author_login": author_login,
                "author_email": author_email,
                "heuristics_matched": heuristics,
                "commit_message_snippet": first_line,
                "full_message": message
            }
            results.append(matched_info)

            try:
                print(f"[{matched_commits_count}] SHA: {short_sha} ({sha})")
                print(f"    Author Name : {author_name}")
                print(f"    Author Login: {author_login}")
                print(f"    Author Email: {author_email}")
                print(f"    Message     : {first_line[:100]}")
                print("    Matched Signatures:")
                for cat, details in heuristics.items():
                    cat_name = cat.split("_", 1)[1].replace("_", " ").title()
                    for d in details:
                        print(f"      - [{cat_name}] {d}")
                print("-" * 80)
            except Exception as e:
                # Safe print fallback if console formatting encounters unprintable chars
                print(f"[{matched_commits_count}] SHA: {short_sha} ({sha}) (Print fallback)")
                print("-" * 80)

    print("\n" + "=" * 80)
    print("SUMMARY OF FINDINGS")
    print("=" * 80)
    print(f"Total Commits Scanned                       : {total_scanned:,}")
    print(f"Total AI/Bot-Assisted Commits Identified    : {matched_commits_count:,} ({ (matched_commits_count/total_scanned*100) if total_scanned else 0:.2f}%)")
    print("\nBreakdown by Git Metadata Signature Category:")
    print(f"  1. Actor Logins Signatures (e.g. [bot])   : {category_counts['1_actor_logins']:,}")
    print(f"  2. Author Email Signatures                : {category_counts['2_author_emails']:,}")
    print(f"  3. Author Name / Identity Signatures      : {category_counts['3_author_names']:,}")
    print(f"  4. Commit Message & Trailer Signatures    : {category_counts['4_commit_trailers']:,}")
    print("=" * 80)

    # Save to JSON artifact file
    output_filename = "openclaw_ai_bot_commits.json"
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump({
            "repo": f"{REPO_OWNER}/{REPO_NAME}",
            "total_scanned": total_scanned,
            "matched_count": matched_commits_count,
            "category_counts": category_counts,
            "matched_commits": results
        }, f, indent=2)
    print(f"\nSaved detailed analysis results to '{output_filename}'")

if __name__ == "__main__":
    main()
