import re
import requests

# Target repository
owner = "openclaw"
repo = "openclaw"
url = f"https://api.github.com/repos/{owner}/{repo}/commits"

# Optional: Add your GitHub Personal Access Token if you hit rate limits
# headers = {"Authorization": "Bearer YOUR_GITHUB_TOKEN"}
headers = {}

print(f"Fetching recent commits from {owner}/{repo} via GitHub API...")
response = requests.get(url, headers=headers, params={"per_page": 300})

if response.status_code != 200:
    print(f"Error fetching data: {response.status_code} - {response.text}")
    exit()

commits = response.json()

# Heuristic patterns based on the paper's methodology
bot_login_pattern = re.compile(r"\[bot\]", re.IGNORECASE)
ai_email_pattern = re.compile(
    r"(noreply@(anthropic|openai|google)\.com|copilot)", re.IGNORECASE
)
ai_name_pattern = re.compile(
    r"(Cursor Agent|Copilot|Claude|Jules)", re.IGNORECASE
)
trailer_pattern = re.compile(r"Co-authored-by:.*", re.IGNORECASE)

ai_detected_count = 0

for commit in commits:
  sha = commit.get("sha", "")[:7]
  commit_data = commit.get("commit", {})
  author_info = commit_data.get("author", {})
  author_name = author_info.get("name", "")
  author_email = author_info.get("email", "")
  message = commit_data.get("message", "")

  # Check actor login / author name / email if available from GitHub user object
  author_login = ""
  if commit.get("author"):
    author_login = commit["author"].get("login", "")

  # 1. Actor Logins / Names / Emails / Trailers check
  is_bot_login = bool(bot_login_pattern.search(author_login))
  is_ai_email = bool(ai_email_pattern.search(author_email))
  is_ai_name = bool(
      ai_name_pattern.search(author_name)
      or ai_name_pattern.search(author_login)
  )
  has_trailer = bool(trailer_pattern.search(message))

  if is_bot_login or is_ai_email or is_ai_name or has_trailer:
    ai_detected_count += 1
    print(f"\n[AI Signature Found] Commit: {sha}")
    print(f"  - Author Name: {author_name} (Login: {author_login})")
    print(f"  - Author Email: {author_email}")
    print(
        f"  - Signatures matched -> Bot Login: {is_bot_login}, AI Email:"
        f" {is_ai_email}, AI Name: {is_ai_name}, Trailer: {has_trailer}"
    )

print(
    f"\nScan complete. Checked {len(commits)} commits, found"
    f" {ai_detected_count} matching AI/bot signatures."
)