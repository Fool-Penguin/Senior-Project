import pathlib

path = pathlib.Path(r"D:\4th-year\Senior-Project\scripts\run_full_scale_benchmark.py")
text = path.read_text(encoding="utf-8")

old_func = '''def retrieve_rag_context(
    collection, code, language, top_k=3, include_kb_snippets=True
):
    """
    Retrieve top-k relevant security catalogue entries from ChromaDB for language.
    Note: RAG is pulled identically regardless of whether the prompt mode is
    zero-shot, one-shot, few-shot, or cot.
    """
    lang = language.lower()
    lines = code.splitlines()
    meaningful_lines = [l for l in lines if not l.strip().startswith(('import ', 'from ', '#', '//', '/*'))]
    query_text = "\\n".join(meaningful_lines)[:2000] if meaningful_lines else code[:2000]

    try:
        results = collection.query(
            query_texts=[query_text],
            where={"language": lang},
            n_results=top_k,
            include=["metadatas", "documents", "distances"],
        )
    except Exception:
        results = collection.query(
            query_texts=[query_text],
            n_results=top_k,
            include=["metadatas", "documents", "distances"],
        )

    context_lines = [f"### Retrieved RAG Knowledge Base Context ({lang}, top_k={top_k}):"]
    metadatas = results["metadatas"][0] if results.get("metadatas") else []

    for m in metadatas:
        cid = m.get("catalogue_id", "")
        cwe = m.get("cwe_id", "")
        name = m.get("cwe_name", "")
        sources = m.get("sources", "N/A")
        sinks = m.get("sinks", "N/A")
        sanitizers = m.get("sanitizers", "N/A")

        rule_block = (
            f"- [{cid}] {cwe} ({name}):\\n"
            f"  * Sources: {sources}\\n"
            f"  * Sinks: {sinks}\\n"
            f"  * Valid Sanitizers: {sanitizers}"
        )
        if include_kb_snippets and m.get("has_example"):
            orig_ex = m.get("example_original_code", "").strip()[:250]
            fixed_ex = m.get("example_fixed_code", "").strip()[:250]
            if orig_ex:
                rule_block += f"\\n  * KB Reference Flaw Pattern:\\n```\\n{orig_ex}\\n```"
            if fixed_ex:
                rule_block += f"\\n  * KB Reference Remediation Pattern:\\n```\\n{fixed_ex}\\n```"

        context_lines.append(rule_block)

    return "\\n\\n".join(context_lines)'''

new_func = '''# Map of CWE -> characteristic sink / API signatures in code (Python, JS, TS)
# Used by Hybrid ChromaDB RAG retrieval to combine dense vector similarity with lexical sink matching
CWE_SINK_SIGNATURES = {
    "CWE-89": [r"\\.execute\\s*\\(", r"\\.query\\s*\\(", r"SELECT\\s+.+FROM", r"INSERT\\s+INTO", r"UPDATE\\s+.+SET", r"DELETE\\s+FROM", r"raw_sql", r"sequelize\\.query", r"cursor\\.execute"],
    "CWE-78": [r"subprocess\\.", r"shell\\s*=\\s*True", r"child_process", r"execSync\\s*\\(", r"spawn\\s*\\(", r"os\\.system\\s*\\(", r"os\\.popen\\s*\\(", r"exec\\s*\\(\\s*[`'\"]"],
    "CWE-77": [r"os\\.system\\s*\\(", r"os\\.popen\\s*\\(", r"subprocess\\.Popen", r"child_process\\.exec", r"execSync"],
    "CWE-79": [r"innerHTML", r"outerHTML", r"document\\.write", r"dangerouslySetInnerHTML", r"render_template_string", r"Markup\\s*\\(", r"res\\.send\\s*\\(", r"res\\.write\\s*\\(", r"<script", r"<img", r"data:text/html"],
    "CWE-94": [r"\\beval\\s*\\(", r"\\bexec\\s*\\(", r"new\\s+Function\\s*\\(", r"compile\\s*\\(", r"vm\\.runIn"],
    "CWE-95": [r"\\beval\\s*\\(", r"new\\s+Function\\s*\\("],
    "CWE-1336": [r"jinja2\\.Template", r"render_template_string", r"ejs\\.render", r"nunjucks\\.renderString", r"handlebars\\.compile", r"pug\\.render"],
    "CWE-943": [r"\\.find\\s*\\(\\s*\\{", r"\\.findOne\\s*\\(\\s*\\{", r"\\$where", r"\\$gt", r"\\$ne", r"mongodb", r"mongoose"],
    "CWE-611": [r"ElementTree\\.fromstring", r"lxml\\.etree", r"parseXml", r"DOMParser", r"xml2js", r"resolve_entities", r"noent\\s*:\\s*true"],
    "CWE-22": [r"\\bopen\\s*\\(", r"send_file\\s*\\(", r"send_from_directory", r"fs\\.readFile", r"fs\\.readFileSync", r"fs\\.createReadStream", r"path\\.join", r"os\\.path\\.join", r"shutil\\.copy", r"Path\\s*\\("],
    "CWE-601": [r"\\bredirect\\s*\\(", r"res\\.redirect", r"window\\.location", r"location\\.href", r"HttpResponseRedirect"],
    "CWE-862": [r"has_permission", r"is_admin", r"check_auth", r"authorize", r"permission", r"@login_required", r"req\\.user", r"current_user", r"role"],
    "CWE-352": [r"csrf", r"CSRFProtect", r"SameSite", r"csurf", r"@csrf_exempt"],
    "CWE-502": [r"pickle\\.loads", r"_pickle\\.loads", r"yaml\\.load\\s*\\(", r"yaml\\.unsafe_load", r"unserialize\\s*\\(", r"jsonpickle", r"marshal\\.loads"],
    "CWE-915": [r"setattr\\s*\\(", r"Object\\.assign\\s*\\(", r"\\*\\*request\\.json", r"\\*\\*req\\.body", r"update_attributes"],
    "CWE-1321": [r"__proto__", r"constructor\\.prototype", r"Object\\.assign", r"merge\\s*\\(", r"deepMerge", r"setattr\\s*\\(", r"__dict__"],
    "CWE-918": [r"requests\\.get\\s*\\(", r"requests\\.post\\s*\\(", r"requests\\.request\\s*\\(", r"urllib\\.request\\.urlopen", r"httpx\\.", r"aiohttp\\.", r"fetch\\s*\\(", r"axios\\."],
    "CWE-798": [r"API_KEY\\s*=", r"SECRET_KEY\\s*=", r"PASSWORD\\s*=", r"password\\s*=\\s*['\"]", r"jwt\\.sign\\s*\\([^,]+,\\s*['\"]", r"aws_secret_access_key"],
    "CWE-327": [r"DES\\b", r"ARC4", r"Blowfish", r"MODE_ECB", r"createCipheriv\\s*\\(\\s*['\"]des", r"rc4", r"aes-\\d+-ecb"],
    "CWE-338": [r"random\\.random\\s*\\(", r"random\\.randint\\s*\\(", r"random\\.choice\\s*\\(", r"Math\\.random\\s*\\("],
    "CWE-328": [r"hashlib\\.md5", r"hashlib\\.sha1", r"createHash\\s*\\(\\s*['\"]md5", r"createHash\\s*\\(\\s*['\"]sha1", r"MD5\\.new", r"SHA\\.new"],
    "CWE-347": [r"jwt\\.decode\\s*\\(", r"verify_signature\\s*:\\s*False", r"options\\s*=\\s*\\{[^}]*verify_signature", r"jwt\\.verify", r"alg.*none"],
    "CWE-209": [r"traceback\\.format_exc", r"debug\\s*=\\s*True", r"err\\.stack", r"error\\.stack", r"printStackTrace"],
    "CWE-1333": [r"re\\.compile\\s*\\(", r"re\\.search\\s*\\(", r"re\\.match\\s*\\(", r"new\\s+RegExp\\s*\\(", r"\\.match\\s*\\(\\s*new\\s+RegExp"],
    "CWE-1427": [r"chat\\.completions\\.create", r"llm\\.invoke", r"PromptTemplate", r"system_prompt", r"messages\\s*=\\s*\\["],
    "CWE-1426": [r"chat\\.completions\\.create", r"llm\\.invoke", r"openai\\.", r"anthropic\\."],
    "CWE-200": [r"jsonify\\s*\\(", r"res\\.json\\s*\\(", r"logging\\.", r"console\\.log", r"system_instructions", r"confidential"],
}


def clean_code_for_rag_query(code: str) -> list:
    """
    1. Strip leading '123| ' line number prefixes (present in GHSA multi-function samples).
    2. Strip pure import / comment lines so ONNXMiniLM_L6_V2's 256-token window focuses on executable statements & sinks.
    3. Return up to 4 overlapping chunks of 900 chars (~220 tokens) so multi-function files are not truncated at line 35.
    """
    cleaned_lines = []
    for line in code.splitlines():
        line_no_num = re.sub(r"^\\s*\\d+\\|\\s?", "", line)
        stripped = line_no_num.strip()
        if not stripped:
            continue
        if stripped.startswith(("import ", "from ", "#", "//", "/*", "*", "*/")):
            continue
        cleaned_lines.append(line_no_num)

    full_cleaned = "\\n".join(cleaned_lines) if cleaned_lines else code
    chunks = []
    step = 750
    for start in range(0, min(len(full_cleaned), 3600), step):
        chunk = full_cleaned[start : start + 900]
        if chunk.strip():
            chunks.append(chunk)
    return chunks or [code[:900]]


def retrieve_rag_context(
    collection, code, language, top_k=3, include_kb_snippets=True
):
    """
    Retrieve top-k relevant security catalogue entries from ChromaDB for language
    using Hybrid Multi-Chunk Vector Search + Lexical Sink-Signature Reranking,
    deduplicated by cwe_id so top_k always provides distinct CWE candidates.
    Note: RAG is pulled identically regardless of whether the prompt mode is
    zero-shot, one-shot, few-shot, or cot.
    """
    lang = language.lower()
    chunks = clean_code_for_rag_query(code)
    candidate_pool_size = max(top_k * 4, 28)

    try:
        results = collection.query(
            query_texts=chunks,
            where={"language": lang},
            n_results=candidate_pool_size,
            include=["metadatas", "documents", "distances"],
        )
    except Exception:
        results = collection.query(
            query_texts=chunks,
            n_results=candidate_pool_size,
            include=["metadatas", "documents", "distances"],
        )

    best_score_by_kb = {}
    meta_by_kb = {}
    all_metadatas = results.get("metadatas") or []
    all_distances = results.get("distances") or []

    for chunk_idx in range(len(all_metadatas)):
        metas = all_metadatas[chunk_idx]
        dists = all_distances[chunk_idx] if chunk_idx < len(all_distances) else [1.0] * len(metas)
        for m, d in zip(metas, dists):
            kid = m.get("kb_id") or m.get("catalogue_id") or str(id(m))
            meta_by_kb[kid] = m
            if kid not in best_score_by_kb or d < best_score_by_kb[kid]:
                best_score_by_kb[kid] = d

    # Apply Sink-Signature Reranking Boost when explicit sink APIs appear in the code
    for kid, m in meta_by_kb.items():
        cwe = m.get("cwe_id", "")
        patterns = CWE_SINK_SIGNATURES.get(cwe, [])
        if patterns:
            match_count = sum(1 for pat in patterns if re.search(pat, code, re.IGNORECASE))
            if match_count > 0:
                best_score_by_kb[kid] -= min(0.35, 0.12 * match_count)

    # Sort by hybrid score and deduplicate by cwe_id so top_k contains distinct CWE rules
    ranked_kids = sorted(best_score_by_kb.keys(), key=lambda k: best_score_by_kb[k])
    selected_metadatas = []
    seen_cwes = set()
    for kid in ranked_kids:
        m = meta_by_kb[kid]
        cwe = m.get("cwe_id", "")
        if cwe and cwe in seen_cwes:
            continue
        if cwe:
            seen_cwes.add(cwe)
        selected_metadatas.append(m)
        if len(selected_metadatas) >= top_k:
            break

    context_lines = [f"### Retrieved RAG Knowledge Base Context ({lang}, top_k={top_k}):"]

    for m in selected_metadatas:
        cid = m.get("catalogue_id", "")
        cwe = m.get("cwe_id", "")
        name = m.get("cwe_name", "")
        sources = m.get("sources", "N/A")
        sinks = m.get("sinks", "N/A")
        sanitizers = m.get("sanitizers", "N/A")

        rule_block = (
            f"- [{cid}] {cwe} ({name}):\\n"
            f"  * Sources: {sources}\\n"
            f"  * Sinks: {sinks}\\n"
            f"  * Valid Sanitizers: {sanitizers}"
        )
        if include_kb_snippets and m.get("has_example"):
            orig_ex = m.get("example_original_code", "").strip()[:250]
            fixed_ex = m.get("example_fixed_code", "").strip()[:250]
            if orig_ex:
                rule_block += f"\\n  * KB Reference Flaw Pattern:\\n```\\n{orig_ex}\\n```"
            if fixed_ex:
                rule_block += f"\\n  * KB Reference Remediation Pattern:\\n```\\n{fixed_ex}\\n```"

        context_lines.append(rule_block)

    return "\\n\\n".join(context_lines)'''

normalized = text.replace("\r\n", "\n")
assert old_func in normalized, "old_func not found in normalized text"
updated = normalized.replace(old_func, new_func, 1)
path.write_text(updated, encoding="utf-8")
print("Successfully updated retrieve_rag_context in run_full_scale_benchmark.py")
