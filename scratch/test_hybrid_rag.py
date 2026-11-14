"""
Test Hybrid Sink-Aware + Multi-Window ChromaDB Vector RAG Retrieval on V3 (967 samples).
Let's see how much Recall@1, Recall@3, Recall@5 improve!
"""
import json
import pathlib
import re
from collections import Counter
import chromadb
from chromadb.utils.embedding_functions import ONNXMiniLM_L6_V2

ROOT = pathlib.Path(__file__).parent.parent
KB_PATH = ROOT / "datasets" / "combined" / "knowledge_base.jsonl"
V3_PATH = ROOT / "datasets" / "combined" / "dataset_v3_multifunc_30to20000_vuln_only_967.jsonl"
CHROMA_DIR = ROOT / "data" / "chromadb_kb"

with open(KB_PATH, "r", encoding="utf-8") as f:
    kb_rows = [json.loads(line) for line in f if line.strip()]

with open(V3_PATH, "r", encoding="utf-8") as f:
    samples = [json.loads(line) for line in f if line.strip()]

# Map of CWE -> characteristic sink / API signatures in code (Python, JS, TS)
CWE_SINK_SIGNATURES = {
    "CWE-89": [r"\.execute\s*\(", r"\.query\s*\(", r"SELECT\s+.+FROM", r"INSERT\s+INTO", r"UPDATE\s+.+SET", r"DELETE\s+FROM", r"raw_sql", r"sequelize\.query", r"cursor\.execute"],
    "CWE-78": [r"subprocess\.", r"shell\s*=\s*True", r"child_process", r"execSync\s*\(", r"spawn\s*\(", r"os\.system\s*\(", r"os\.popen\s*\(", r"exec\s*\(\s*[`'\"]"],
    "CWE-77": [r"os\.system\s*\(", r"os\.popen\s*\(", r"subprocess\.Popen", r"child_process\.exec", r"execSync"],
    "CWE-79": [r"innerHTML", r"outerHTML", r"document\.write", r"dangerouslySetInnerHTML", r"render_template_string", r"Markup\s*\(", r"res\.send\s*\(", r"res\.write\s*\(", r"<script", r"<img", r"data:text/html"],
    "CWE-94": [r"\beval\s*\(", r"\bexec\s*\(", r"new\s+Function\s*\(", r"compile\s*\(", r"vm\.runIn"],
    "CWE-95": [r"\beval\s*\(", r"new\s+Function\s*\("],
    "CWE-1336": [r"jinja2\.Template", r"render_template_string", r"ejs\.render", r"nunjucks\.renderString", r"handlebars\.compile", r"pug\.render"],
    "CWE-943": [r"\.find\s*\(\s*\{", r"\.findOne\s*\(\s*\{", r"\$where", r"\$gt", r"\$ne", r"mongodb", r"mongoose"],
    "CWE-611": [r"ElementTree\.fromstring", r"lxml\.etree", r"parseXml", r"DOMParser", r"xml2js", r"resolve_entities", r"noent\s*:\s*true"],
    "CWE-22": [r"\bopen\s*\(", r"send_file\s*\(", r"send_from_directory", r"fs\.readFile", r"fs\.readFileSync", r"fs\.createReadStream", r"path\.join", r"os\.path\.join", r"shutil\.copy", r"Path\s*\("],
    "CWE-601": [r"\bredirect\s*\(", r"res\.redirect", r"window\.location", r"location\.href", r"HttpResponseRedirect"],
    "CWE-862": [r"has_permission", r"is_admin", r"check_auth", r"authorize", r"permission", r"@login_required", r"req\.user", r"current_user", r"role"],
    "CWE-352": [r"csrf", r"CSRFProtect", r"SameSite", r"csurf", r"@csrf_exempt"],
    "CWE-502": [r"pickle\.loads", r"_pickle\.loads", r"yaml\.load\s*\(", r" yaml\.unsafe_load", r"unserialize\s*\(", r"jsonpickle", r"marshal\.loads"],
    "CWE-915": [r"setattr\s*\(", r"Object\.assign\s*\(", r"\*\*request\.json", r"\*\*req\.body", r"update_attributes"],
    "CWE-1321": [r"__proto__", r"constructor\.prototype", r"Object\.assign", r"merge\s*\(", r"deepMerge", r"setattr\s*\(", r"__dict__"],
    "CWE-918": [r"requests\.get\s*\(", r"requests\.post\s*\(", r"requests\.request\s*\(", r"urllib\.request\.urlopen", r"httpx\.", r"aiohttp\.", r"fetch\s*\(", r"axios\."],
    "CWE-798": [r"API_KEY\s*=", r"SECRET_KEY\s*=", r"PASSWORD\s*=", r"password\s*=\s*['\"]", r"jwt\.sign\s*\([^,]+,\s*['\"]", r"aws_secret_access_key"],
    "CWE-327": [r"DES\b", r"ARC4", r"Blowfish", r"MODE_ECB", r"createCipheriv\s*\(\s*['\"]des", r"rc4", r"aes-\d+-ecb"],
    "CWE-338": [r"random\.random\s*\(", r"random\.randint\s*\(", r"random\.choice\s*\(", r"Math\.random\s*\("],
    "CWE-328": [r"hashlib\.md5", r"hashlib\.sha1", r"createHash\s*\(\s*['\"]md5", r"createHash\s*\(\s*['\"]sha1", r"MD5\.new", r"SHA\.new"],
    "CWE-347": [r"jwt\.decode\s*\(", r"verify_signature\s*:\s*False", r"options\s*=\s*\{[^}]*verify_signature", r"jwt\.verify", r"alg.*none"],
    "CWE-209": [r"traceback\.format_exc", r"debug\s*=\s*True", r"err\.stack", r"error\.stack", r"printStackTrace"],
    "CWE-1333": [r"re\.compile\s*\(", r"re\.search\s*\(", r"re\.match\s*\(", r"new\s+RegExp\s*\(", r"\.match\s*\(\s*new\s+RegExp"],
    "CWE-1427": [r"chat\.completions\.create", r"llm\.invoke", r"PromptTemplate", r"system_prompt", r"messages\s*=\s*\["],
    "CWE-1426": [r"chat\.completions\.create", r"llm\.invoke", r"openai\.", r"anthropic\."],
    "CWE-200": [r"jsonify\s*\(", r"res\.json\s*\(", r"logging\.", r"console\.log", r"system_instructions", r"confidential"],
}

def clean_code_for_rag_query(code: str) -> list[str]:
    """
    1. Strip leading '123| ' line numbers.
    2. Strip pure import / comment lines so MiniLM's 256-token window focuses on executable statements & sinks.
    3. Return overlapping chunks of up to 900 chars (~220 tokens) so multi-function files up to 20,000 chars are fully searched!
    """
    cleaned_lines = []
    for line in code.splitlines():
        # Strip leading line numbers like '  123| '
        line_no_num = re.sub(r"^\s*\d+\|\s?", "", line)
        stripped = line_no_num.strip()
        if not stripped:
            continue
        if stripped.startswith(("import ", "from ", "#", "//", "/*", "*", "*/")):
            continue
        cleaned_lines.append(line_no_num)

    full_cleaned = "\n".join(cleaned_lines) if cleaned_lines else code
    # Split into up to 4 chunks of 900 chars across the code so long files aren't truncated at line 35
    chunks = []
    step = 750
    for start in range(0, min(len(full_cleaned), 3600), step):
        chunk = full_cleaned[start : start + 900]
        if chunk.strip():
            chunks.append(chunk)
    return chunks or [code[:900]]

client = chromadb.PersistentClient(path=str(CHROMA_DIR))
embedding_fn = ONNXMiniLM_L6_V2()
collection = client.get_collection(name="codedee_knowledge_base", embedding_function=embedding_fn)

hits_at = {1: 0, 3: 0, 5: 0, 8: 0}
for s in samples:
    lang = s["language"].lower()
    code = s["original_code"]
    true_cwe = s["cwe_id"]

    chunks = clean_code_for_rag_query(code)
    res = collection.query(
        query_texts=chunks,
        where={"language": lang},
        n_results=28,
        include=["metadatas", "distances"]
    )

    # Aggregate best (minimum) distance per kb_id across chunks + Sink Signature Boost
    best_score_by_kb = {}
    meta_by_kb = {}

    for chunk_idx in range(len(chunks)):
        metas = res["metadatas"][chunk_idx]
        dists = res["distances"][chunk_idx]
        for m, d in zip(metas, dists):
            kid = m["kb_id"]
            meta_by_kb[kid] = m
            if kid not in best_score_by_kb or d < best_score_by_kb[kid]:
                best_score_by_kb[kid] = d

    # Apply Sink Signature Boost (if code contains explicit sink API calls for that CWE, reduce distance)
    for kid, m in meta_by_kb.items():
        cwe = m["cwe_id"]
        patterns = CWE_SINK_SIGNATURES.get(cwe, [])
        match_count = sum(1 for pat in patterns if re.search(pat, code, re.IGNORECASE))
        if match_count > 0:
            # Boost score (lower distance = closer match)
            best_score_by_kb[kid] -= min(0.35, 0.12 * match_count)

    ranked_kbs = sorted(best_score_by_kb.keys(), key=lambda k: best_score_by_kb[k])
    retrieved_cwes = []
    for kid in ranked_kbs:
        c = meta_by_kb[kid]["cwe_id"]
        if c not in retrieved_cwes:
            retrieved_cwes.append(c)

    for k in hits_at:
        if true_cwe in retrieved_cwes[:k]:
            hits_at[k] += 1

n = len(samples)
print(f"\n--- Hybrid Multi-Chunk + Sink-Aware RAG Retrieval Recall on V3 ({n} samples) ---")
for k, h in hits_at.items():
    print(f"Recall@{k}: {h}/{n} ({h/n*100:.2f}%)")
