import os
import requests
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

OPENROUTER_BASE_URL = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openrouter/free")

SYSTEM_PROMPT = """You are PR Commentary — an elite, opinionated code reviewer with 20 years of experience at top tech companies.

Your job: review code diffs and deliver feedback that is:
1. **Actionable** — every issue has a clear fix
2. **Educational** — explain WHY something is a problem
3. **Concise** — get to the point, no waffle
4. **Honest** — flag real bugs, not nitpicks

Format your response as markdown. Structure it like this:

## 🔴 Critical Issues (fix before merge)
[Issues that could cause bugs, security problems, or production failures]

## 🟡 Worth Discussing (nitpicks with rationale)
[Issues that aren't bugs but are worth reconsidering — naming, design choices, etc.]

## 🟢 Looks Good
[What the author got right — genuine praise, not filler]

## 💡 Suggestions
[Optional improvements: better patterns, alternative approaches]

Be specific. Reference actual line numbers or function names from the diff.
If something is truly excellent, say so directly.
"""

def call_openrouter(prompt: str) -> str:
    """Call OpenRouter API with the given prompt."""
    if not OPENROUTER_API_KEY:
        return "❌ OpenRouter API key not configured. Set OPENROUTER_API_KEY in environment."
    
    try:
        response = requests.post(
            f"{OPENROUTER_BASE_URL}/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": OPENROUTER_MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.3,
                "max_tokens": 2000,
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"]
    except requests.exceptions.Timeout:
        return "❌ Request timed out. The AI model took too long to respond. Try a smaller diff."
    except requests.exceptions.HTTPError as e:
        if response.status_code == 401:
            return "❌ Authentication failed. Check your OPENROUTER_API_KEY."
        elif response.status_code == 429:
            return "❌ Rate limited. Please wait a moment and try again."
        return f"❌ API error: {e}"
    except Exception as e:
        return f"❌ Unexpected error: {e}"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/review", methods=["POST"])
def review():
    data = request.get_json()
    diff = (data.get("diff") or "").strip()
    pr_url = (data.get("pr_url") or "").strip()
    
    if not diff and not pr_url:
        return jsonify({"error": "Please provide a diff or PR URL."}), 400
    
    # Build the prompt
    if pr_url and not diff:
        prompt = f"Please review this GitHub PR:\n{pr_url}\n\nI don't have the diff content — can you give general advice on what to look for in a PR review?"
    elif diff:
        prompt = f"Please review this code diff:\n\n```\n{diff}\n```"
    else:
        prompt = f"Review this PR (URL: {pr_url}) with this diff:\n\n```\n{diff}\n```"
    
    result = call_openrouter(prompt)
    return jsonify({"review": result})


@app.route("/health")
def health():
    return jsonify({"status": "ok"})
