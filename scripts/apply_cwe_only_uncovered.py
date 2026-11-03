import csv
import os

uncovered_rows = [
    {
        "No.": "1",
        "Type": "Injection",
        "Name": "Static Code Injection (Statically Saved Directives)",
        "Description": "Code syntax injected into a static configuration or template file saved on disk and executed out-of-band by another component.",
        "References": "CWE-96",
        "Exclusion Rationale": "Multi-Stage Persistence Boundary: Involves writing to disk executed out-of-band by secondary runtimes/cron, breaking direct in-memory taint analysis."
    },
    {
        "No.": "",
        "Type": "Injection",
        "Name": "XPath Injection",
        "Description": "Untrusted input concatenated into XML XPath query expressions altering query logic.",
        "References": "CWE-643",
        "Exclusion Rationale": "Stack Irrelevance: Near-zero prevalence in modern Python/JS/TS web ecosystems (REST/JSON/GraphQL supersede XML databases)."
    },
    {
        "No.": "",
        "Type": "Injection",
        "Name": "LDAP Injection",
        "Description": "Untrusted input concatenated into LDAP directory query strings allowing authentication bypass.",
        "References": "CWE-90",
        "Exclusion Rationale": "Protocol Obsolescence: Enterprise identity systems use OAuth2/OIDC/SAML; raw LDAP socket querying is outside modern web app scope."
    },
    {
        "No.": "",
        "Type": "Injection",
        "Name": "XML Injection (Blind XPath / Syntax Injection)",
        "Description": "Untrusted data modifying the tag structure of XML documents without entity parsing.",
        "References": "CWE-91",
        "Exclusion Rationale": "Superseded by XXE (CWE-611): Parser attacks in modern runtimes target entity resolution rather than generic tag syntax alteration."
    },
    {
        "No.": "",
        "Type": "Injection",
        "Name": "Server-Side Includes (SSI) Injection",
        "Description": "Untrusted input injected into HTML directives executed by web server SSI modules.",
        "References": "CWE-97",
        "Exclusion Rationale": "Obsolete Technology: Apache mod_include directives are obsolete and superseded by modern server-side template engines (Jinja2/EJS)."
    },
    {
        "No.": "2",
        "Type": "Broken Access Control",
        "Name": "Incorrect Authorization",
        "Description": "Authorization checks exist but evaluate permissions incorrectly based on dynamic tenant roles.",
        "References": "CWE-863",
        "Exclusion Rationale": "Dynamic State Dependency: Complex multi-tenant organizational hierarchies reside in dynamic database records inaccessible to static source ASTs."
    },
    {
        "No.": "",
        "Type": "Broken Access Control",
        "Name": "Insecure Direct Object Reference (IDOR)",
        "Description": "Attacker modifies a key or database ID in request parameters to access other tenant records.",
        "References": "CWE-639",
        "Exclusion Rationale": "Database Correlation Required: Identifying that ID 1042 belongs to Tenant B requires runtime database query correlation rather than code syntax checks."
    },
    {
        "No.": "3",
        "Type": "Authentication Failures",
        "Name": "Missing Authentication for Critical Function",
        "Description": "Web application endpoints fail to verify user identity prior to executing business actions.",
        "References": "CWE-306",
        "Exclusion Rationale": "Subjective Business Intent: Determining if an endpoint (e.g. /healthz or /catalog) requires auth requires undocumented business specs; flagging all leads to >85% false alarms."
    },
    {
        "No.": "",
        "Type": "Authentication Failures",
        "Name": "Improper Authentication / Password Complexity",
        "Description": "Weak password complexity requirements, credential stuffing vulnerabilities, or missing MFA.",
        "References": "CWE-287 / CWE-521",
        "Exclusion Rationale": "Enterprise IdP Policy: Authentication policy and MFA enforcement reside in external Identity Providers (Auth0, Okta, Cognito) rather than application code."
    },
    {
        "No.": "",
        "Type": "Authentication Failures",
        "Name": "Improper Certificate Validation",
        "Description": "Application fails to validate trust chains or expiration dates of TLS client certificates.",
        "References": "CWE-295",
        "Exclusion Rationale": "Managed Runtime Delegation: Python and Node runtimes delegate trust store verification to the host operating system root CA store."
    },
    {
        "No.": "4",
        "Type": "Cryptographic Failures",
        "Name": "Cleartext Transmission of Sensitive Information",
        "Description": "Application transmits sensitive credentials or data over unencrypted HTTP channels.",
        "References": "CWE-319",
        "Exclusion Rationale": "Ingress Deployment Layer: Modern cloud containers terminate TLS at ingress load balancers (Nginx/ALB); application containers legitimately listen on internal HTTP."
    },
    {
        "No.": "",
        "Type": "Cryptographic Failures",
        "Name": "Inadequate Encryption Strength / Key Length",
        "Description": "Use of RSA key lengths less than 2048 bits or ECC less than 256 bits.",
        "References": "CWE-326",
        "Exclusion Rationale": "Key Vault Infrastructure: Cryptographic keys in modern cloud architectures are managed via cloud KMS (AWS KMS/Vault) rather than raw code ASTs."
    },
    {
        "No.": "5",
        "Type": "Security Misconfiguration",
        "Name": "Default Account Credentials in Server Daemon",
        "Description": "Default administrative passwords left enabled in underlying database or message broker.",
        "References": "CWE-16",
        "Exclusion Rationale": "Infrastructure Daemon Configuration: Database server configuration files (postgresql.conf) reside outside application source code repositories."
    },
    {
        "No.": "",
        "Type": "Security Misconfiguration",
        "Name": "Permissive Cross-Origin Resource Sharing (CORS)",
        "Description": "Access-Control-Allow-Origin header configured with wildcard (*) allowing untrusted sites to read data.",
        "References": "CWE-942",
        "Exclusion Rationale": "Gateway/CDN Enforcement: CORS policies are enforced at the API gateway or CDN edge layer rather than in first-party application source ASTs."
    },
    {
        "No.": "6",
        "Type": "Insecure Design",
        "Name": "HTTP Request Smuggling",
        "Description": "Inconsistent interpretation of Content-Length vs Transfer-Encoding between frontend proxy and backend.",
        "References": "CWE-444",
        "Exclusion Rationale": "Reverse-Proxy Infrastructure Layer: Caused by network gateway and load balancer RFC 7230 parsing desync outside application source code."
    },
    {
        "No.": "",
        "Type": "Insecure Design",
        "Name": "Regular Expression Denial of Service (ReDoS)",
        "Description": "Vulnerable regular expressions with nested quantifiers cause exponential catastrophic backtracking.",
        "References": "CWE-400 / CWE-1333",
        "Exclusion Rationale": "Algorithmic Complexity & GIL Boundary: In MITRE, ReDoS is a child of CWE-400 (Uncontrolled Resource Consumption). Excluded from AST SAST because algorithmic execution timing depends on runtime engine backtracking."
    },
    {
        "No.": "7",
        "Type": "Software & Data Integrity Failures",
        "Name": "Download of Code Without Integrity Check",
        "Description": "Application downloads executable scripts or binaries from remote sources without cryptographic hash check.",
        "References": "CWE-494",
        "Exclusion Rationale": "DevOps / Build Pipeline Boundary: Governed by CI/CD package managers and container builders rather than web application request routing logic."
    }
]

fieldnames = ["No.", "Type", "Name", "Description", "References", "Exclusion Rationale"]

for filepath in ["Uncovered_Taxonomy_table.csv", "data/Uncovered_Taxonomy_table.csv"]:
    os.makedirs(os.path.dirname(filepath), exist_ok=True) if os.path.dirname(filepath) else None
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_MINIMAL)
        writer.writeheader()
        writer.writerows(uncovered_rows)
    print(f"Wrote {len(uncovered_rows)} rows to {filepath}")
