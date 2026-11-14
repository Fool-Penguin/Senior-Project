import os

html_content = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CodeDEE - Senior Project I Proposal Presentation (15 Mins)</title>
    <style>
        :root {
            --bg-primary: #070b14;
            --bg-secondary: #0f172a;
            --bg-card: #1e293b;
            --text-main: #f8fafc;
            --text-sub: #94a3b8;
            --accent-cyan: #06b6d4;
            --accent-blue: #3b82f6;
            --accent-indigo: #6366f1;
            --accent-green: #10b981;
            --accent-amber: #f59e0b;
            --accent-rose: #f43f5e;
            --border-color: #334155;
        }

        * {
            box-sizing: border-box;
            margin: 0;
            padding: 0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
        }

        body {
            background-color: var(--bg-primary);
            color: var(--text-main);
            height: 100vh;
            overflow: hidden;
            display: flex;
            flex-direction: column;
        }

        /* Top Bar */
        .top-bar {
            height: 54px;
            background: rgba(15, 23, 42, 0.95);
            backdrop-filter: blur(10px);
            border-bottom: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 24px;
            z-index: 100;
        }

        .brand-title {
            display: flex;
            align-items: center;
            gap: 12px;
            font-size: 1.1rem;
            font-weight: 700;
            color: var(--accent-cyan);
            letter-spacing: 0.5px;
        }

        .brand-title span.badge {
            font-size: 0.72rem;
            padding: 3px 8px;
            border-radius: 4px;
            background: rgba(6, 182, 212, 0.15);
            border: 1px solid rgba(6, 182, 212, 0.4);
            color: var(--accent-cyan);
            font-weight: 600;
        }

        .timer-container {
            display: flex;
            align-items: center;
            gap: 16px;
        }

        .timer-display {
            font-family: "Courier New", Courier, monospace;
            font-size: 1.25rem;
            font-weight: 700;
            color: #10b981;
            background: #020617;
            padding: 4px 14px;
            border-radius: 6px;
            border: 1px solid #1e293b;
            min-width: 90px;
            text-align: center;
        }

        .timer-display.warning {
            color: #f59e0b;
            border-color: #f59e0b;
        }

        .timer-display.danger {
            color: #f43f5e;
            border-color: #f43f5e;
            animation: pulse 1s infinite;
        }

        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }

        .top-controls {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .btn {
            background: #1e293b;
            border: 1px solid var(--border-color);
            color: var(--text-main);
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 0.8rem;
            cursor: pointer;
            transition: all 0.2s ease;
            display: inline-flex;
            align-items: center;
            gap: 6px;
        }

        .btn:hover {
            background: #334155;
            border-color: var(--accent-cyan);
            color: #fff;
        }

        .btn.active {
            background: var(--accent-blue);
            border-color: var(--accent-blue);
            color: #fff;
        }

        /* Slide Container */
        .stage-container {
            flex: 1;
            display: flex;
            position: relative;
            overflow: hidden;
        }

        .slide-deck {
            flex: 1;
            position: relative;
            display: flex;
            justify-content: center;
            align-items: center;
            padding: 24px;
            overflow-y: auto;
        }

        .slide {
            display: none;
            width: 100%;
            max-width: 1200px;
            height: calc(100vh - 120px);
            background: #0c1222;
            border: 1px solid #1e293b;
            border-radius: 12px;
            padding: 36px 44px;
            position: relative;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.6);
            flex-direction: column;
            overflow-y: auto;
        }

        .slide.active {
            display: flex;
            animation: fadeIn 0.25s ease-out;
        }

        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(6px); }
            to { opacity: 1; transform: translateY(0); }
        }

        .slide-header {
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 24px;
            border-bottom: 1px solid #1e293b;
            padding-bottom: 14px;
        }

        .slide-meta {
            font-size: 0.8rem;
            color: var(--accent-cyan);
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 4px;
        }

        .slide-title {
            font-size: 1.85rem;
            font-weight: 800;
            color: #ffffff;
            letter-spacing: -0.5px;
        }

        .slide-num-pill {
            font-size: 0.85rem;
            font-weight: 700;
            background: #1e293b;
            color: var(--text-sub);
            padding: 4px 12px;
            border-radius: 20px;
            border: 1px solid var(--border-color);
        }

        .slide-body {
            flex: 1;
            display: flex;
            flex-direction: column;
            justify-content: center;
        }

        /* Teleprompter / Speaker Drawer */
        .teleprompter-drawer {
            width: 380px;
            background: #090e1a;
            border-left: 1px solid var(--border-color);
            display: flex;
            flex-direction: column;
            transition: all 0.3s ease;
            z-index: 90;
        }

        .teleprompter-drawer.collapsed {
            width: 0;
            display: none;
        }

        .drawer-header {
            padding: 14px 18px;
            background: #0f172a;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }

        .drawer-header h3 {
            font-size: 0.95rem;
            color: var(--accent-cyan);
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .drawer-content {
            padding: 20px;
            overflow-y: auto;
            flex: 1;
            font-size: 0.92rem;
            line-height: 1.65;
            color: #e2e8f0;
        }

        .script-box {
            background: #131d31;
            border-left: 4px solid var(--accent-cyan);
            padding: 14px 16px;
            border-radius: 0 8px 8px 0;
            margin-bottom: 16px;
            font-style: normal;
        }

        .tip-box {
            background: rgba(16, 185, 129, 0.1);
            border: 1px solid rgba(16, 185, 129, 0.3);
            border-radius: 8px;
            padding: 12px 14px;
            font-size: 0.82rem;
            color: #6ee7b7;
        }

        /* Slide Content Components */
        .grid-2 {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
            height: 100%;
            align-items: center;
        }

        .grid-3 {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
            height: 100%;
            align-items: center;
        }

        .card {
            background: #141c2e;
            border: 1px solid #27354f;
            border-radius: 10px;
            padding: 20px;
            height: 100%;
            display: flex;
            flex-direction: column;
            justify-content: flex-start;
        }

        .card h4 {
            color: var(--accent-cyan);
            font-size: 1.15rem;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .card p, .card li {
            font-size: 0.95rem;
            color: #cbd5e1;
            line-height: 1.55;
            margin-bottom: 8px;
        }

        .card ul {
            padding-left: 20px;
        }

        .badge-pill {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.75rem;
            font-weight: 700;
            margin-right: 6px;
        }

        .badge-cyan { background: rgba(6, 182, 212, 0.2); color: #22d3ee; border: 1px solid rgba(6, 182, 212, 0.4); }
        .badge-blue { background: rgba(59, 130, 246, 0.2); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.4); }
        .badge-green { background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4); }
        .badge-amber { background: rgba(245, 158, 11, 0.2); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.4); }
        .badge-rose { background: rgba(244, 63, 94, 0.2); color: #fb7185; border: 1px solid rgba(244, 63, 94, 0.4); }

        .img-container {
            width: 100%;
            height: 100%;
            display: flex;
            justify-content: center;
            align-items: center;
            overflow: hidden;
            border-radius: 8px;
            background: #090e1a;
            border: 1px solid #1e293b;
        }

        .img-container img {
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
        }

        table.presentation-table {
            width: 100%;
            border-collapse: collapse;
            font-size: 0.88rem;
            background: #101726;
            border-radius: 8px;
            overflow: hidden;
        }

        table.presentation-table th {
            background: #1e293b;
            color: var(--accent-cyan);
            padding: 10px 14px;
            text-align: left;
            font-weight: 700;
            border-bottom: 2px solid #334155;
        }

        table.presentation-table td {
            padding: 10px 14px;
            border-bottom: 1px solid #1e293b;
            color: #cbd5e1;
        }

        table.presentation-table tr:hover td {
            background: #172033;
        }

        /* Bottom Controls */
        .bottom-bar {
            height: 48px;
            background: #0a0e1a;
            border-top: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            justify-content: space-between;
            padding: 0 24px;
            font-size: 0.8rem;
            color: var(--text-sub);
        }

        .progress-bar-container {
            flex: 1;
            height: 6px;
            background: #1e293b;
            border-radius: 3px;
            margin: 0 24px;
            overflow: hidden;
        }

        .progress-bar-fill {
            height: 100%;
            background: linear-gradient(90deg, var(--accent-cyan), var(--accent-blue));
            width: 5%;
            transition: width 0.3s ease;
        }
    </style>
</head>
<body>

    <!-- Top Bar -->
    <div class="top-bar">
        <div class="brand-title">
            <span>CodeDEE</span>
            <span class="badge">Senior Project I Proposal</span>
            <span style="font-size: 0.8rem; color: #94a3b8; font-weight: normal;">ICT Mahidol University</span>
        </div>

        <div class="timer-container">
            <span style="font-size: 0.78rem; color: var(--text-sub); font-weight: 600;">PRESENTER TIMER:</span>
            <div class="timer-display" id="timer">15:00</div>
            <button class="btn" id="timerToggleBtn" onclick="toggleTimer()">▶ Start</button>
            <button class="btn" onclick="resetTimer()">↺ Reset</button>
        </div>

        <div class="top-controls">
            <button class="btn" id="drawerToggleBtn" onclick="toggleTeleprompter()">🎙️ Speaker Script (P)</button>
            <button class="btn" onclick="toggleFullscreen()">⛶ Fullscreen (F)</button>
        </div>
    </div>

    <!-- Main Stage -->
    <div class="stage-container">
        <div class="slide-deck" id="slideDeck">

            <!-- Slide 1 -->
            <div class="slide active" data-index="1" data-time="0:40" data-script="Good morning, respected committee members and advisor Prof. Kookaip. Today, our team—Ongsa, Thanadon, and Brook—presents our Senior Project I proposal entitled CodeDEE: An In-Editor Dual-Lens Engine for Continuous Maintainability Analysis and Neuro-Symbolic Security Program Repair. In this 15-minute presentation, we will walk you through our motivation, system architecture, methodology, preliminary benchmarks, and Semester 2 roadmap." data-tip="Open with a confident, measured tone. Make eye contact with Prof. Kookaip and the examiners.">
                <div class="slide-header">
                    <div>
                        <div class="slide-meta">Proposal Examination • 27 November 2026</div>
                        <h2 class="slide-title">CodeDEE</h2>
                    </div>
                    <div class="slide-num-pill">Slide 1 / 18</div>
                </div>
                <div class="slide-body">
                    <div style="text-align: center; max-width: 900px; margin: 0 auto;">
                        <h3 style="font-size: 1.5rem; color: var(--accent-cyan); margin-bottom: 16px; font-weight: 600;">
                            A Tool for Analyzing Code Maintainability and Security in Web Applications Developed with Python, JavaScript, and TypeScript
                        </h3>
                        <p style="font-size: 1.1rem; color: #94a3b8; margin-bottom: 32px;">
                            Faculty of Information and Communication Technology, Mahidol University
                        </p>
                        <div style="display: flex; justify-content: center; gap: 32px; margin-bottom: 40px;">
                            <div class="card" style="padding: 16px 24px; min-width: 220px; text-align: left;">
                                <div style="font-weight: 700; color: #fff;">Ongsa</div>
                                <div style="font-size: 0.85rem; color: var(--accent-cyan);">Lead Architect & Security</div>
                            </div>
                            <div class="card" style="padding: 16px 24px; min-width: 220px; text-align: left;">
                                <div style="font-weight: 700; color: #fff;">Thanadon Yindeesuk</div>
                                <div style="font-size: 0.85rem; color: var(--accent-blue);">Maintainability & LSP</div>
                            </div>
                            <div class="card" style="padding: 16px 24px; min-width: 220px; text-align: left;">
                                <div style="font-weight: 700; color: #fff;">Brook</div>
                                <div style="font-size: 0.85rem; color: var(--accent-green);">RAG & Evaluation</div>
                            </div>
                        </div>
                        <div style="display: inline-block; background: rgba(59, 130, 246, 0.1); border: 1px solid rgba(59, 130, 246, 0.3); padding: 8px 24px; border-radius: 20px;">
                            <span style="color: #94a3b8;">Advisor:</span> <strong style="color: #60a5fa;">Prof. Kookaip</strong>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Slide 2 -->
            <div class="slide" data-index="2" data-time="1:25" data-script="Modern web applications evolve at an unprecedented speed. Today's software stacks are predominantly polyglot, heavily relying on Python for backend APIs and JavaScript or TypeScript for dynamic frontends. Under tight Agile sprint deadlines, developers face a constant tug-of-war. As features are pushed rapidly, codebases suffer from severe technical debt—cyclomatic complexity explodes, functions become deeply nested, and architectural coupling increases. Simultaneously, because these systems are directly exposed to the internet, developers inadvertently introduce critical security flaws like injection and insecure deserialization. The core dilemma is that developers must juggle maintainability and security simultaneously, without unified tooling to support them." data-tip="Emphasize that modern developers cannot choose between speed, security, and maintainability—they must manage all three.">
                <div class="slide-header">
                    <div>
                        <div class="slide-meta">Motivation & Background</div>
                        <h2 class="slide-title">The Double Burden of Modern Web Development</h2>
                    </div>
                    <div class="slide-num-pill">Slide 2 / 18</div>
                </div>
                <div class="slide-body">
                    <div class="grid-2">
                        <div class="card">
                            <h4>🌐 Polyglot Ecosystem Dynamics</h4>
                            <p><strong>Primary Languages:</strong> Python, JavaScript, and TypeScript represent over 70% of modern web backend and frontend development.</p>
                            <p><strong>Fast-Paced Agile Delivery:</strong> Continuous delivery cycles demand rapid feature commits, often sidelining deep architectural reviews.</p>
                            <p><strong>Compound Vulnerability Surface:</strong> Public internet exposure means any structural oversight or insecure input directly threatens system integrity.</p>
                        </div>
                        <div class="card">
                            <h4>⚠️ The Accumulating Dual Debt</h4>
                            <div style="background: rgba(244, 63, 94, 0.1); border-left: 4px solid var(--accent-rose); padding: 12px; margin-bottom: 12px; border-radius: 4px;">
                                <strong style="color: var(--accent-rose);">1. Maintainability Degradation:</strong> Functions become bloated (LOC > 60), McCabe Cyclomatic Complexity exceeds thresholds, and modules become tightly coupled.
                            </div>
                            <div style="background: rgba(245, 158, 11, 0.1); border-left: 4px solid var(--accent-amber); padding: 12px; border-radius: 4px;">
                                <strong style="color: var(--accent-amber);">2. Critical Security Exposure:</strong> Injection (SQLi, Commandi), Cross-Site Scripting (XSS), Server-Side Request Forgery (SSRF), and broken access controls emerge undetected.
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Slide 3 -->
            <div class="slide" data-index="3" data-time="2:15" data-script="When investigating why these issues persist in modern engineering teams, we identified three critical industry pain points. First: Tool Fragmentation. Maintainability and security are treated as two separate worlds. Developers must run different linters, security scanners, and CI/CD jobs, each reporting in isolated formats with zero correlation. Second: Alert Fatigue without Actionable Solutions. Traditional static analysis tools flag hundreds of warnings, but they provide zero context-aware repair code. Developers spend hours manually investigating warnings or simply dismiss them. Third: The AI Hallucination Trap. While developers now use LLMs like ChatGPT or Copilot to assist with fixes, raw generative AI lacks deterministic boundaries—often producing invalid syntax, breaking existing code semantics, or introducing secondary security vulnerabilities. CodeDEE was engineered specifically to solve these three gaps." data-tip="Call out the contrast clearly: traditional linters only complain, while raw LLMs hallucinate. CodeDEE bridges both.">
                <div class="slide-header">
                    <div>
                        <div class="slide-meta">Problem Statement</div>
                        <h2 class="slide-title">3 Core Industry Pain Points in Current Workflows</h2>
                    </div>
                    <div class="slide-num-pill">Slide 3 / 18</div>
                </div>
                <div class="slide-body">
                    <div class="grid-3">
                        <div class="card">
                            <span class="badge-pill badge-rose">Pain Point 1</span>
                            <h4 style="margin-top: 10px;">Siloed & Fragmented Tooling</h4>
                            <p>Maintainability (linters/SonarQube) and security (SAST scanners) operate in total isolation.</p>
                            <ul>
                                <li>Disparate configuration files</li>
                                <li>Conflicting rule definitions</li>
                                <li>No unified code health score</li>
                                <li>High developer context-switching</li>
                            </ul>
                        </div>
                        <div class="card">
                            <span class="badge-pill badge-amber">Pain Point 2</span>
                            <h4 style="margin-top: 10px;">Alert Fatigue & No Actionable Fixes</h4>
                            <p>Traditional SAST produces massive unranked lists of warnings without repair code.</p>
                            <ul>
                                <li>High false positive rate on custom logic</li>
                                <li>Zero context-aware patch synthesis</li>
                                <li>Developers spend hours researching fixes</li>
                                <li>Critical alerts get routinely ignored</li>
                            </ul>
                        </div>
                        <div class="card">
                            <span class="badge-pill badge-cyan">Pain Point 3</span>
                            <h4 style="margin-top: 10px;">The AI Hallucination & Regression Trap</h4>
                            <p>Commercial LLMs (Copilot, ChatGPT) generate code without deterministic safety bounds.</p>
                            <ul>
                                <li>Hallucinates syntax and unimported APIs</li>
                                <li>Fixes one bug while introducing another</li>
                                <li>Violates internal project coding standards</li>
                                <li>Proprietary IP leaked to cloud APIs</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Slide 4 -->
            <div class="slide" data-index="4" data-time="3:00" data-script="To address this problem, our project defines four concrete, action-driven objectives: First, to investigate and formalize a unified code quality framework combining 8 standard ISO/IEC 25010 maintainability metrics with a targeted 28-vulnerability security taxonomy across Python, JavaScript, and TypeScript. Second, to develop a hybrid Neuro-Symbolic analysis engine that pairs deterministic taint propagation graphs with a dense local RAG knowledge base and an LLM Neural Oracle to verify vulnerabilities without alert fatigue. Third, to design a closed-loop multi-gate verification pipeline that automatically synthesizes repair patches and proves they compile, eradicate the vulnerability, and improve code structure before reaching the developer. And fourth, to build and deploy this entire solution as an in-editor VS Code extension powered by the Language Server Protocol for seamless, zero-friction developer adoption." data-tip="Emphasize the action verbs: Investigate, Develop, Design, Build.">
                <div class="slide-header">
                    <div>
                        <div class="slide-meta">Project Foundation</div>
                        <h2 class="slide-title">Objectives of the Project</h2>
                    </div>
                    <div class="slide-num-pill">Slide 4 / 18</div>
                </div>
                <div class="slide-body">
                    <div class="grid-2">
                        <div class="card">
                            <span class="badge-pill badge-cyan">Objective 1 • Formalize</span>
                            <h4 style="margin-top: 10px;">Unified Quality & Security Framework</h4>
                            <p>Formulate an integrated taxonomy combining <strong>8 ISO/IEC 25010 maintainability metrics</strong> with <strong>28 CWE/OWASP web vulnerability rules</strong> for Python, JS, and TS.</p>
                        </div>
                        <div class="card">
                            <span class="badge-pill badge-blue">Objective 2 • Develop</span>
                            <h4 style="margin-top: 10px;">Neuro-Symbolic Analysis Engine</h4>
                            <p>Construct a hybrid engine pairing deterministic graph taint propagation (CFG/DFG) with a dense local ChromaDB RAG and an LLM Neural Oracle to eliminate false alarms.</p>
                        </div>
                        <div class="card">
                            <span class="badge-pill badge-green">Objective 3 • Design</span>
                            <h4 style="margin-top: 10px;">Closed-Loop Multi-Gate Auto-Fix Verifier</h4>
                            <p>Engineer an automated repair pipeline enforcing strict multi-gate validation (Syntax, Security Flaw, Maintainability Non-Regression) with bounded retries (k < 3).</p>
                        </div>
                        <div class="card">
                            <span class="badge-pill badge-amber">Objective 4 • Build</span>
                            <h4 style="margin-top: 10px;">In-Editor VS Code Extension via LSP</h4>
                            <p>Deliver non-blocking, continuous feedback and one-click patch actions directly inside the developer's IDE using the open Language Server Protocol.</p>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Slide 5 -->
            <div class="slide" data-index="5" data-time="3:45" data-script="To ensure academic rigor and feasibility within our one-year timeline, we have precisely established the project scope. CodeDEE targets the primary languages of modern web engineering: Python, JavaScript, and TypeScript. Our maintainability scope rigorously implements 8 standardized metrics mapped to the ISO/IEC 25010 software quality model. Our security scope focuses on a curated taxonomy of 28 high-impact web vulnerabilities mapped directly to CWE and OWASP standards. Crucially, CodeDEE operates entirely in a local, offline environment using local Small Language Models. No source code or proprietary IP ever leaves the developer's workstation. Conversely, runtime dynamic fuzzing, binary analysis, and whole-organization repository migration are strictly out of scope, allowing us to deliver a focused, high-precision developer tool." data-tip="Be clear on boundaries: local execution means 100% data privacy. Out-of-scope boundaries demonstrate maturity.">
                <div class="slide-header">
                    <div>
                        <div class="slide-meta">Project Foundation</div>
                        <h2 class="slide-title">Scope of Work & System Boundaries</h2>
                    </div>
                    <div class="slide-num-pill">Slide 5 / 18</div>
                </div>
                <div class="slide-body">
                    <div class="grid-2">
                        <div class="card" style="border-top: 4px solid var(--accent-green);">
                            <h4 style="color: var(--accent-green);">✅ In-Scope Target Deliverables</h4>
                            <ul>
                                <li><strong>Target Languages:</strong> Python (3.9+), JavaScript (ES6+), and TypeScript (4.5+).</li>
                                <li><strong>Maintainability Scope:</strong> 8 ISO/IEC 25010 metrics (CC, Cognitive, Halstead Difficulty, LOC, SLOC, LCOM4, Ca, Ce).</li>
                                <li><strong>Security Scope:</strong> 28 curated web application CWEs mapped to OWASP Top 10 (Injection, SSRF, XSS, Broken Auth, Path Traversal, Insecure Deserialization).</li>
                                <li><strong>Execution Privacy:</strong> 100% local offline execution (Ollama SLMs, zero data leakage).</li>
                                <li><strong>IDE Environment:</strong> Visual Studio Code via Language Server Protocol (LSP).</li>
                            </ul>
                        </div>
                        <div class="card" style="border-top: 4px solid var(--accent-rose);">
                            <h4 style="color: var(--accent-rose);">❌ Explicit System Boundaries (Out of Scope)</h4>
                            <ul>
                                <li><strong>Dynamic Runtime Fuzzing (DAST):</strong> Focus is strictly static and intermediate semantic graph analysis.</li>
                                <li><strong>Compiled Binary / Native Code:</strong> C/C++, Rust, or Go binaries are excluded.</li>
                                <li><strong>Whole-Repository Automated Monolithic Refactoring:</strong> Targets modular function and file-level repairs.</li>
                                <li><strong>Hardware / Microarchitectural Vulnerabilities:</strong> Side-channel attacks (Spectre/Meltdown) are out of scope.</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Slide 6 -->
            <div class="slide" data-index="6" data-time="4:30" data-script="The expected benefits of CodeDEE span both everyday developer productivity and high-level organizational security. For the developer, CodeDEE provides a 'single pane of glass'. Instead of switching between five terminal tools, maintainability warnings and security flaws appear instantly in the VS Code editor. Because our engine performs closed-loop verification, developers do not just receive complaints—they receive ready-to-merge, verified code patches. For organizations, CodeDEE truly operationalizes the 'Shift-Left' paradigm. Detecting vulnerabilities at authoring time rather than during late-stage penetration tests prevents costly deployment delays. Furthermore, because our entire neural and symbolic stack runs on local hardware, organizations maintain complete data sovereignty with zero proprietary source code leaked to third-party cloud APIs." data-tip="Highlight 'Shift-Left' and 'Zero Data Leakage' as high-value organizational benefits.">
                <div class="slide-header">
                    <div>
                        <div class="slide-meta">Project Foundation</div>
                        <h2 class="slide-title">Expected Benefits & Strategic Impact</h2>
                    </div>
                    <div class="slide-num-pill">Slide 6 / 18</div>
                </div>
                <div class="slide-body">
                    <div class="grid-2">
                        <div class="card">
                            <h4>👨‍💻 For Software Developers</h4>
                            <ul>
                                <li><strong>Single Pane of Glass:</strong> Instant, unified maintainability and security feedback inside VS Code gutter and problems panel within seconds.</li>
                                <li><strong>Elimination of Alert Fatigue:</strong> Deterministic Base Severity combined with Contextual Risk filtering cuts triage time by > 60%.</li>
                                <li><strong>One-Click Verified Repairs:</strong> Verified diffs guaranteed not to introduce syntax errors, regress security, or bloat complexity.</li>
                            </ul>
                        </div>
                        <div class="card">
                            <h4>🏢 For Organizations & Research</h4>
                            <ul>
                                <li><strong>True 'Shift-Left' Quality:</strong> Bugs caught during typing rather than during late CI/CD bottlenecks or expensive security penetration tests.</li>
                                <li><strong>Zero Data Leakage:</strong> Air-gapped, fully local execution compliant with enterprise intellectual property and privacy mandates.</li>
                                <li><strong>Reproducible Benchmark:</strong> 5 standardized open datasets and repeatable evaluation frameworks for the academic community.</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Slide 7 -->
            <div class="slide" data-index="7" data-time="5:30" data-script="Let us examine where existing industry solutions stand. Tools like SonarQube excel at maintainability metrics but offer weak security taint tracking and cannot generate verified contextual fixes. Security scanners like Semgrep, Snyk, and GitHub CodeQL provide deep vulnerability detection, but they are purely diagnostic—they point out flaws without automated repair, and they completely ignore structural maintainability. On the other end of the spectrum, commercial generative AI assistants like GitHub Copilot can draft code, but they lack deterministic program analysis, frequently hallucinating uncompilable code or subtle logic bugs. As shown in this competitive matrix, CodeDEE represents the first system to unify maintainability and security through a hybrid Neuro-Symbolic approach, closing the loop with automated, multi-gate verified patch synthesis." data-tip="Point to the 'CodeDEE (Ours)' column. Every checkmark represents an intentional architectural advantage.">
                <div class="slide-header">
                    <div>
                        <div class="slide-meta">Literature Review & Benchmarking</div>
                        <h2 class="slide-title">Related Works & Competitive Matrix</h2>
                    </div>
                    <div class="slide-num-pill">Slide 7 / 18</div>
                </div>
                <div class="slide-body">
                    <table class="presentation-table">
                        <thead>
                            <tr>
                                <th>Capability / Dimension</th>
                                <th>SonarQube</th>
                                <th>Semgrep / Snyk</th>
                                <th>CodeQL (GitHub)</th>
                                <th>Copilot / Raw LLMs</th>
                                <th style="color: #22d3ee; background: #172554;">CodeDEE (Ours)</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td><strong>Analysis Scope</strong></td>
                                <td>Maintainability + Rules</td>
                                <td>Pure SAST Security</td>
                                <td>Deep Semantic Security</td>
                                <td>Generic Generation</td>
                                <td style="color: #38bdf8; font-weight: 700;">Unified Maintainability + Security</td>
                            </tr>
                            <tr>
                                <td><strong>Underlying Paradigm</strong></td>
                                <td>Pure AST & Regex</td>
                                <td>Pattern Matching</td>
                                <td>QL Relational Logic</td>
                                <td>Stochastic Black-Box</td>
                                <td style="color: #38bdf8; font-weight: 700;">Neuro-Symbolic (Graph + RAG + SLM)</td>
                            </tr>
                            <tr>
                                <td><strong>Automated Auto-Fix</strong></td>
                                <td>❌ None (Docs Only)</td>
                                <td>⚠️ Basic Regex Rules</td>
                                <td>❌ Manual Fix Needed</td>
                                <td>⚠️ Unverified / Hallucinates</td>
                                <td style="color: #38bdf8; font-weight: 700;">✅ Multi-Gate Verified Patches</td>
                            </tr>
                            <tr>
                                <td><strong>Verification Loop</strong></td>
                                <td>❌ None</td>
                                <td>❌ None</td>
                                <td>❌ None</td>
                                <td>❌ None</td>
                                <td style="color: #38bdf8; font-weight: 700;">✅ Syntax + Security + Metrics (k < 3)</td>
                            </tr>
                            <tr>
                                <td><strong>Execution Privacy</strong></td>
                                <td>Cloud / Server</td>
                                <td>Cloud / Local CLI</td>
                                <td>Enterprise Cloud</td>
                                <td>External Cloud API</td>
                                <td style="color: #38bdf8; font-weight: 700;">✅ 100% Local & Offline (LSP)</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Slide 8 -->
            <div class="slide" data-index="8" data-time="6:20" data-script="Here is how CodeDEE operates from end to end across five modular stages. When a developer writes or edits code, Stage 1 parses the file using Tree-sitter into a Concrete Syntax Tree, preserving full formatting and whitespace. Stage 2 constructs language-agnostic intermediate graph models: Control Flow Graphs, Data Flow Graphs, Call Graphs, and Import Dependency Graphs. Next, the engine splits into two concurrent streams: Stream 3A calculates 8 ISO 25010 maintainability metrics deterministically, while Stream 3B performs symbolic taint propagation. If a taint path reaches a dangerous sink, it extracts a contextual program slice and invokes our local RAG-assisted Neural Oracle to verify whether it is a true vulnerability or sanitized. If an issue is confirmed, Stage 4 generates an automated fix and runs it through a closed-loop multi-gate verifier. Once verified, Stage 5 displays interactive diagnostics and one-click patch actions inside the editor." data-tip="Walk left-to-right through the 5 stages. Be clear on when symbolic logic ends and neural verification begins.">
                <div class="slide-header">
                    <div>
                        <div class="slide-meta">System Design</div>
                        <h2 class="slide-title">Proposed Solution: The CodeDEE Pipeline</h2>
                    </div>
                    <div class="slide-num-pill">Slide 8 / 18</div>
                </div>
                <div class="slide-body">
                    <div style="display: flex; gap: 12px; height: 100%; align-items: stretch;">
                        <div class="card" style="flex: 1; padding: 14px;">
                            <span class="badge-pill badge-cyan">Stage 1</span>
                            <h4 style="font-size: 0.95rem; margin-top: 8px;">Code Ingestion & Parsing</h4>
                            <p style="font-size: 0.85rem;">Tree-sitter incremental parser constructs lossless Concrete Syntax Trees (CST).</p>
                        </div>
                        <div class="card" style="flex: 1; padding: 14px;">
                            <span class="badge-pill badge-blue">Stage 2</span>
                            <h4 style="font-size: 0.95rem; margin-top: 8px;">Intermediate Graphs</h4>
                            <p style="font-size: 0.85rem;">CFG, DFG, Call Graph, and Module Import Graph built via NetworkX.</p>
                        </div>
                        <div class="card" style="flex: 1.2; padding: 14px; background: #172554; border-color: #2563eb;">
                            <span class="badge-pill badge-amber">Stage 3 (Dual)</span>
                            <h4 style="font-size: 0.95rem; margin-top: 8px;">Parallel Analysis</h4>
                            <p style="font-size: 0.82rem;"><strong>3A:</strong> 8 ISO Maintainability Metrics.<br><strong>3B:</strong> Symbolic Taint Walker + Program Slicer + Dense RAG + Neural Oracle.</p>
                        </div>
                        <div class="card" style="flex: 1; padding: 14px; background: #064e3b; border-color: #059669;">
                            <span class="badge-pill badge-green">Stage 4</span>
                            <h4 style="font-size: 0.95rem; margin-top: 8px;">Multi-Gate Auto-Fix</h4>
                            <p style="font-size: 0.85rem;">Synthesizes patches validated by Syntax, Security, and Metrics gates (k < 3).</p>
                        </div>
                        <div class="card" style="flex: 1; padding: 14px;">
                            <span class="badge-pill badge-rose">Stage 5</span>
                            <h4 style="font-size: 0.95rem; margin-top: 8px;">In-Editor Presentation</h4>
                            <p style="font-size: 0.85rem;">LSP diagnostics, gutter squiggles, side-by-side diff viewer, and 1-click apply.</p>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Slide 9 -->
            <div class="slide" data-index="9" data-time="7:30" data-script="Slide 9 illustrates the official System Architecture of CodeDEE, structured into two decoupled swimlanes communicating over the standard Language Server Protocol. The upper swimlane represents the VS Code Extension Client. It listens to editor buffer events, renders inline warnings, and hosts the visual patch diff inspector. The lower swimlane is the CodeDEE Local Analysis Engine. Because we communicate over LSP using JSON-RPC, the developer's editing interface remains completely non-blocking and fluid while heavy computations execute asynchronously in the background. Inside the engine, source files are parsed by Tree-sitter and converted into four intermediate graphs. The maintainability pipeline computes structural scores, while the security pipeline executes taint propagation and program slicing. Notice our local ChromaDB knowledge base: it enriches the LLM prompt with exact CWE remediation rules, ensuring deterministic grounding without cloud dependencies." data-tip="Refer explicitly to 'Figure 3.2'. Point out the clean boundary between VS Code Client and the LSP Engine.">
                <div class="slide-header">
                    <div>
                        <div class="slide-meta">System Architecture • Figure 3.2</div>
                        <h2 class="slide-title">System Architecture: Two-Swimlane LSP Design</h2>
                    </div>
                    <div class="slide-num-pill">Slide 9 / 18</div>
                </div>
                <div class="slide-body">
                    <div class="img-container">
                        <img src="figure_3_2_system_architecture.png" alt="CodeDEE System Architecture Diagram">
                    </div>
                </div>
            </div>

            <!-- Slide 10 -->
            <div class="slide" data-index="10" data-time="8:25" data-script="To ensure clean software engineering standards and modular team development, we structured the CodeDEE architecture into a three-level Functional Decomposition Diagram, shown here in Slide 10. Under the root CodeDEE system, functionality is partitioned into six distinct, cohesive subsystems: Subsystem 1.0 handles multi-language syntax parsing; Subsystem 2.0 builds the graph representations; Subsystem 3.0 handles all maintainability metrics; Subsystem 4.0 governs the neuro-symbolic security audit; Subsystem 5.0 manages automated patch synthesis and multi-gate validation; and Subsystem 6.0 handles IDE integration and LSP communication. This modular decomposition guarantees that each subsystem can be developed, tested, and benchmarked independently with strict interfaces between team members." data-tip="Refer explicitly to 'Figure 3.1'. Emphasize how Subsystems 1 through 6 map directly to team member specializations.">
                <div class="slide-header">
                    <div>
                        <div class="slide-meta">Functional Decomposition • Figure 3.1</div>
                        <h2 class="slide-title">Functional Decomposition Diagram (FDD)</h2>
                    </div>
                    <div class="slide-num-pill">Slide 10 / 18</div>
                </div>
                <div class="slide-body">
                    <div class="img-container">
                        <img src="figure_3_1_functional_decomposition.png" alt="CodeDEE Functional Decomposition Diagram">
                    </div>
                </div>
            </div>

            <!-- Slide 11 -->
            <div class="slide" data-index="11" data-time="9:25" data-script="Slide 11 details our first analysis lens: the Maintainability Engine. Rather than relying on arbitrary ad-hoc heuristics, we strictly adopt the international ISO/IEC 25010 software product quality standard, mapping metrics across Analysability, Modifiability, Modularity, and Reusability. For example, under Analysability, we compute McCabe's Cyclomatic Complexity with a threshold of 10 for branch paths, combined with Cognitive Complexity with a threshold of 15 to penalize deeply nested code that taxes human working memory. Under Modularity, we implement LCOM4 via connected component analysis of class method-field graphs—any value greater than 1 signals an immediate candidate for class decomposition. These metrics are 100% deterministic, computed in milliseconds directly over our intermediate graphs without needing any LLM overhead." data-tip="Explain that maintainability is 100% deterministic math. No LLM hallucination is possible here.">
                <div class="slide-header">
                    <div>
                        <div class="slide-meta">Methodology • Lens 1</div>
                        <h2 class="slide-title">Maintainability Engine: 8 ISO/IEC 25010 Metrics</h2>
                    </div>
                    <div class="slide-num-pill">Slide 11 / 18</div>
                </div>
                <div class="slide-body">
                    <table class="presentation-table">
                        <thead>
                            <tr>
                                <th>ISO/IEC 25010 Category</th>
                                <th>Target Metric</th>
                                <th>Scope</th>
                                <th>Threshold</th>
                                <th>Scientific Rationale & Derivation</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td><strong>Analysability</strong></td>
                                <td>Cyclomatic Complexity (CC)</td>
                                <td>Function</td>
                                <td>> 10</td>
                                <td>McCabe (1976); linear basis paths; exponential defect rise</td>
                            </tr>
                            <tr>
                                <td><strong>Analysability</strong></td>
                                <td>Cognitive Complexity</td>
                                <td>Function</td>
                                <td>> 15</td>
                                <td>SonarSource standard; penalizes mental nesting overhead</td>
                            </tr>
                            <tr>
                                <td><strong>Modifiability</strong></td>
                                <td>Halstead Difficulty (D)</td>
                                <td>Function</td>
                                <td>> 30</td>
                                <td>Halstead (1977); operator/operand vocabulary density</td>
                            </tr>
                            <tr>
                                <td><strong>Modifiability</strong></td>
                                <td>Lines of Code (LOC / SLOC)</td>
                                <td>Func / File</td>
                                <td>> 60 / > 500</td>
                                <td>Architectural hygiene; prevents monolithic god-functions</td>
                            </tr>
                            <tr>
                                <td><strong>Modularity</strong></td>
                                <td>LCOM4</td>
                                <td>Class</td>
                                <td>> 1</td>
                                <td>Hitz & Montazeri; disjoint method-field graph components</td>
                            </tr>
                            <tr>
                                <td><strong>Reusability</strong></td>
                                <td>Afferent / Efferent Coupling</td>
                                <td>Module</td>
                                <td>> 20 / > 15</td>
                                <td>Robert C. Martin; incoming stability vs. outgoing fragility</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Slide 12 -->
            <div class="slide" data-index="12" data-time="10:40" data-script="Slide 12 covers our second lens: the Neuro-Symbolic Security Engine. Why do we use a Neuro-Symbolic architecture? Pure static analysis tools are notoriously plagued by false positives because they cannot understand custom sanitization logic or complex string formatting. On the other hand, feeding an entire codebase into a raw LLM causes severe hallucination, prompt truncation, and privacy risks. CodeDEE solves this with a two-step hybrid approach: First, our Symbolic Taint Walker deterministically maps sources to sinks across the Data Flow Graph. If a potential taint path is found, our Program Slicer isolates only the relevant causal lines. Second, our Local ChromaDB RAG retrieves the exact matching remediation rule from our curated 84-rule knowledge base. The code slice and the RAG rule are fed into a local Small Language Model—our Neural Oracle—which acts as an intelligent judge. The Oracle determines whether custom sanitizers exist, assigns a calibrated Contextual Risk score, and eliminates false positives." data-tip="Stress the contrast between Base Severity (symbolic anchor) and Contextual Risk (neural judgment).">
                <div class="slide-header">
                    <div>
                        <div class="slide-meta">Methodology • Lens 2</div>
                        <h2 class="slide-title">Neuro-Symbolic Security Engine & Dense RAG</h2>
                    </div>
                    <div class="slide-num-pill">Slide 12 / 18</div>
                </div>
                <div class="slide-body">
                    <div class="grid-2">
                        <div class="card">
                            <h4>⚙️ Step 1: Symbolic Taint & Slicing</h4>
                            <p><strong>Source-to-Sink Taint Walker:</strong> Deterministically tracks untrusted inputs (<code>req.body</code>, <code>input()</code>) to vulnerable execution sinks (<code>cursor.execute</code>, <code>eval()</code>, <code>res.send()</code>).</p>
                            <p><strong>Causal Program Slicer:</strong> Strips away irrelevant surrounding boilerplate, extracting only the causal data-flow slice (< 50 lines).</p>
                            <div style="background: #1e293b; padding: 10px; border-radius: 6px; font-size: 0.85rem; color: #38bdf8;">
                                🔒 <em>Base Severity Anchor:</em> Theoretical CVSS severity stored in Catalogue anchors against hallucinations.
                            </div>
                        </div>
                        <div class="card">
                            <h4>🧠 Step 2: Dense RAG & Neural Oracle</h4>
                            <p><strong>ChromaDB Local Vector Store:</strong> Indexed with <strong>84 curated CWE/OWASP rules</strong> using <code>all-MiniLM-L6-v2</code> embeddings for instant semantic retrieval.</p>
                            <p><strong>Local SLM Neural Oracle:</strong> Small Language Model (e.g., Foundation-Sec-8B, Qwen2.5-Coder) assesses custom sanitizers.</p>
                            <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); padding: 10px; border-radius: 6px; font-size: 0.85rem; color: #34d399;">
                                🎯 <em>Contextual Risk Score:</em> Evaluates true exploitability to eradicate alert fatigue.
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Slide 13 -->
            <div class="slide" data-index="13" data-time="11:45" data-script="Slide 13 highlights one of CodeDEE's most significant innovations: the Closed-Loop Multi-Gate Auto-Fix Verifier. The biggest complaint software engineers have with AI tools like Copilot is that suggested fixes often introduce syntax errors or break existing behavior. CodeDEE enforces a strict zero-trust policy: no generated patch is ever shown to the developer until it passes three sequential verification gates. Gate 1 verifies Syntax Validity using Tree-sitter to ensure the patch parses without error. Gate 2 verifies Security Remediation by running our Symbolic Taint Walker over the patched code; if the taint path to the sink still persists, the patch is rejected. Gate 3 verifies Maintainability Non-Regression, ensuring the fix did not bloat complexity or introduce spaghetti logic. As shown in the diagram, if a gate fails, CodeDEE triggers a bounded retry loop, passing the failure diagnostics back to the LLM to refine the patch. We cap retries at k < 3 to eliminate infinite loops and ensure guaranteed termination." data-tip="The bounded retry loop (k < 3) directly addresses the committee's concern about infinite loops.">
                <div class="slide-header">
                    <div>
                        <div class="slide-meta">Methodology • Stage 4</div>
                        <h2 class="slide-title">Closed-Loop Multi-Gate Auto-Fix Verifier</h2>
                    </div>
                    <div class="slide-num-pill">Slide 13 / 18</div>
                </div>
                <div class="slide-body">
                    <div class="grid-3" style="margin-bottom: 20px;">
                        <div class="card" style="border-top: 4px solid var(--accent-cyan);">
                            <span class="badge-pill badge-cyan">Gate 1</span>
                            <h4 style="margin-top: 8px;">Syntax Validity Gate</h4>
                            <p style="font-size: 0.88rem;">Re-parses the generated patch using Tree-sitter CST.</p>
                            <p style="color: #94a3b8; font-size: 0.82rem;">❌ Rejects unclosed brackets, invalid grammar, and malformed statements.</p>
                        </div>
                        <div class="card" style="border-top: 4px solid var(--accent-rose);">
                            <span class="badge-pill badge-rose">Gate 2</span>
                            <h4 style="margin-top: 8px;">Security Flaw Removal</h4>
                            <p style="font-size: 0.88rem;">Re-runs Symbolic Taint Walker over the patched code.</p>
                            <p style="color: #94a3b8; font-size: 0.82rem;">❌ Rejects patches where taint still reaches the dangerous execution sink.</p>
                        </div>
                        <div class="card" style="border-top: 4px solid var(--accent-amber);">
                            <span class="badge-pill badge-amber">Gate 3</span>
                            <h4 style="margin-top: 8px;">Maintainability Guard</h4>
                            <p style="font-size: 0.88rem;">Re-computes CC, Cognitive Complexity, and SLOC.</p>
                            <p style="color: #94a3b8; font-size: 0.82rem;">❌ Rejects bloated patches that inflate cyclomatic complexity or introduce dead code.</p>
                        </div>
                    </div>
                    <div class="card" style="background: rgba(99, 102, 241, 0.1); border: 1px solid rgba(99, 102, 241, 0.4); padding: 14px;">
                        <strong style="color: #a5b4fc;">🔄 Bounded Retry Loop Controller (k < 3):</strong>
                        <span style="color: #cbd5e1; font-size: 0.88rem;">
                            If any gate fails, precise diagnostic feedback is injected back into the LLM prompt. If k = 3 without passing all gates, auto-fix gracefully aborts and falls back to diagnostic warning—guaranteeing termination and zero hang time.
                        </span>
                    </div>
                </div>
            </div>

            <!-- Slide 14 -->
            <div class="slide" data-index="14" data-time="12:40" data-script="Now let us turn to our Preliminary Work completed during Semester 1. To evaluate our engine with scientific rigor, we curated five distinct benchmark dataset versions, totaling thousands of verified samples across Python, JavaScript, and TypeScript. As shown on the slide, our primary benchmark is Dataset V4, containing 1,911 balanced samples—comprising 967 vulnerable functions and 944 developer-patched safe controls. Balancing vulnerable code with safe code is absolutely crucial to benchmark whether an engine produces false alarms on clean code. Furthermore, we extracted an external validation set of 507 real-world samples from Meta's CyberSecEval, ensuring our models are tested against independent external benchmarks beyond our primary dataset." data-tip="Emphasize that Dataset V4 has 944 negative safe controls—this is what makes our research methodologically sound.">
                <div class="slide-header">
                    <div>
                        <div class="slide-meta">Preliminary Work • Empirical Datasets</div>
                        <h2 class="slide-title">5 Benchmark Datasets (V1–V4 + CyberSecEval)</h2>
                    </div>
                    <div class="slide-num-pill">Slide 14 / 18</div>
                </div>
                <div class="slide-body">
                    <div class="grid-2">
                        <div class="img-container">
                            <img src="dataset_comparison_v4_vs_cyberseceval.png" alt="Dataset V4 vs CyberSecEval Comparison">
                        </div>
                        <div class="card">
                            <h4>📊 Standardized Benchmark Hierarchy</h4>
                            <ul>
                                <li><strong>V1 (Raw Unfiltered):</strong> 1,208 raw multi-language samples.</li>
                                <li><strong>V2 (Length-Filtered):</strong> 928 samples (30–4,000 chars, 28 taxonomy CWEs).</li>
                                <li><strong>V3 (Multi-Function):</strong> 967 samples (up to 20,000 chars / ~320 lines) capturing realistic helper context.</li>
                                <li><strong>V4 (Balanced Benchmark):</strong> <strong style="color: var(--accent-cyan);">1,911 samples</strong> (967 vulnerable + <strong>944 safe developer-patched controls</strong> with CWE-NONE).</li>
                                <li><strong>CyberSecEval Benchmark:</strong> <strong style="color: var(--accent-green);">507 external real-world samples</strong> from Meta's PurpleLlama benchmark matching our 28 taxonomy CWEs.</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Slide 15 -->
            <div class="slide" data-index="15" data-time="13:30" data-script="In our preliminary model benchmarks, we tested 13 candidate open-source models using our local NVIDIA RTX 5080 GPU infrastructure with an expanded 8,192 token context window. We evaluated models across three tiers: lightweight 1.5B to 3B models, balanced 7B to 8B models, and high-capacity 14B models. Our preliminary findings demonstrate two vital conclusions: First, domain-specialized security models like Foundation-Sec-8B and reasoning models like DeepSeek-R1-8B significantly outperform generic models in distinguishing sanitized code from vulnerable code when guided by ChromaDB RAG. Second, 8-billion parameter models can run entirely inside 16GB of local VRAM, delivering inference times under 1.5 seconds per code slice—confirming that local, zero-cloud in-editor execution is fully feasible." data-tip="The 8,192 token context window guarantees 300-line multi-function code slices are never cut off.">
                <div class="slide-header">
                    <div>
                        <div class="slide-meta">Preliminary Work • Empirical SLM Benchmarks</div>
                        <h2 class="slide-title">Local Model Benchmarking (13 Candidate SLMs)</h2>
                    </div>
                    <div class="slide-num-pill">Slide 15 / 18</div>
                </div>
                <div class="slide-body">
                    <div class="grid-2">
                        <div class="card">
                            <h4>💻 Benchmark Testbed & Setup</h4>
                            <p><strong>Hardware Infrastructure:</strong> NVIDIA GeForce RTX 5080 Laptop GPU (16,303 MiB VRAM), 16 GB RAM.</p>
                            <p><strong>Zero Cloud Dependency:</strong> Ollama local inference runtime.</p>
                            <p><strong>Expanded Context Window:</strong> Configured <code>num_ctx = 8192</code> to process multi-function files up to 320 lines without truncation.</p>
                            <p><strong>Regex Reasoning Filter:</strong> Automatically strips <code>&lt;think&gt;...&lt;/think&gt;</code> blocks for clean JSON parsing.</p>
                        </div>
                        <div class="card">
                            <h4>🎯 13 Models Across 3 Size Tiers</h4>
                            <p><strong>Tier 1 (1.5B–3B):</strong> Qwen2.5-Coder-1.5B/3B, Llama-3.2-3B (Ultra-fast, lower reasoning).</p>
                            <p><strong>Tier 2 (7B–8B, Sweet Spot):</strong> <span class="badge-pill badge-green">Recommended</span> Foundation-Sec-8B (Instruct & Reasoning), DeepSeek-R1-8B, Qwen2.5-Coder-7B, Llama-3.1-8B.</p>
                            <p><strong>Tier 3 (14B):</strong> Qwen2.5-Coder-14B, DeepSeek-R1-14B (Highest capacity, ~4s latency).</p>
                            <div style="background: rgba(16, 185, 129, 0.1); border-left: 3px solid var(--accent-green); padding: 8px; margin-top: 10px; font-size: 0.85rem; color: #a7f3d0;">
                                💡 <em>Key Result:</em> 8B models provide optimal tradeoff (< 1.5s latency, fits fully in VRAM, zero data leakage).
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Slide 16 -->
            <div class="slide" data-index="16" data-time="14:10" data-script="In accordance with our advisor Prof. Kookaip's guidance, we maintain strict academic honesty regarding what has been completed in Senior Project I versus what is scheduled for Senior Project II. In Semester 1, we successfully completed the comprehensive architectural designs, the FDD decomposition, the formalization of our 8 maintainability metrics and 28 security CWE taxonomy, the construction of the 84-rule ChromaDB knowledge base, and the curation of 5 benchmark datasets with preliminary local LLM evaluations. In Semester 2, we will focus entirely on implementing the end-to-end Python/TypeScript engine, integrating the Tree-sitter graph builder, connecting the Multi-Gate Verifier, and deploying the VS Code extension via the Language Server Protocol." data-tip="Examiners appreciate honesty. Clearly distinguishing 'designed' from 'implemented' scores high marks.">
                <div class="slide-header">
                    <div>
                        <div class="slide-meta">Implementation Status</div>
                        <h2 class="slide-title">Semester 1 Accomplished vs. Semester 2 Scope</h2>
                    </div>
                    <div class="slide-num-pill">Slide 16 / 18</div>
                </div>
                <div class="slide-body">
                    <table class="presentation-table">
                        <thead>
                            <tr>
                                <th>System Component</th>
                                <th style="color: #34d399;">Semester 1 (Senior Project I) — COMPLETED</th>
                                <th style="color: #60a5fa;">Semester 2 (Senior Project II) — SCHEDULED</th>
                            </tr>
                        </thead>
                        <tbody>
                            <tr>
                                <td><strong>System Architecture & FDD</strong></td>
                                <td>✅ Complete 2-swimlane LSP design & 6-subsystem FDD</td>
                                <td>🔨 Production integration & profiling</td>
                            </tr>
                            <tr>
                                <td><strong>Maintainability Metrics</strong></td>
                                <td>✅ 8 ISO/IEC 25010 metrics formalized with thresholds</td>
                                <td>🔨 AST graph metric calculation engines</td>
                            </tr>
                            <tr>
                                <td><strong>Security Knowledge Base</strong></td>
                                <td>✅ 84 curated CWE/OWASP rules indexed in ChromaDB</td>
                                <td>🔨 Runtime cache & vector search tuning</td>
                            </tr>
                            <tr>
                                <td><strong>Datasets & Benchmarking</strong></td>
                                <td>✅ 5 curated datasets (V1–V4 + CyberSecEval, 1,911 samples)</td>
                                <td>🔨 Full benchmark evaluation over all 13 models</td>
                            </tr>
                            <tr>
                                <td><strong>Multi-Gate Auto-Fix</strong></td>
                                <td>✅ 3-Gate verification algorithm & bounded retry (k < 3)</td>
                                <td>🔨 Live AST synthesizer integration</td>
                            </tr>
                            <tr>
                                <td><strong>IDE Extension</strong></td>
                                <td>✅ LSP protocol specification & UI mockups</td>
                                <td>🔨 Full VS Code marketplace package & UI diff</td>
                            </tr>
                        </tbody>
                    </table>
                </div>
            </div>

            <!-- Slide 17 -->
            <div class="slide" data-index="17" data-time="14:45" data-script="Slide 17 outlines our 16-week execution plan for Semester 2. The first four weeks will establish the Tree-sitter graph builders. Weeks 5 through 8 will integrate the dual maintainability and security streams. Weeks 9 through 11 will implement the closed-loop Multi-Gate Verifier, followed by full VS Code LSP extension development in weeks 12 through 14, and final benchmarking in weeks 15 and 16. We have also designed proactive risk mitigations: to ensure the editor never lags, analysis tasks run asynchronously with debounced event listeners, and inter-procedural taint propagation is strictly bounded to a depth of three to eliminate algorithmic complexity spikes." data-tip="Reassure the committee that technical risks have already been identified and mitigated.">
                <div class="slide-header">
                    <div>
                        <div class="slide-meta">Project Management</div>
                        <h2 class="slide-title">Semester 2 Work Plan & Risk Mitigation</h2>
                    </div>
                    <div class="slide-num-pill">Slide 17 / 18</div>
                </div>
                <div class="slide-body">
                    <div class="grid-2">
                        <div class="card">
                            <h4>📅 16-Week Semester 2 Milestone Timeline</h4>
                            <ul>
                                <li><strong>Weeks 1–4:</strong> Tree-sitter parsers & intermediate graph modeling (CFG, DFG, Call Graph).</li>
                                <li><strong>Weeks 5–8:</strong> Maintainability calculators & Neuro-Symbolic taint walker with ChromaDB RAG.</li>
                                <li><strong>Weeks 9–11:</strong> Closed-loop Multi-Gate Auto-Fix verifier & bounded retry loop.</li>
                                <li><strong>Weeks 12–14:</strong> Full VS Code LSP Extension development & interactive diff viewer.</li>
                                <li><strong>Weeks 15–16:</strong> Comprehensive benchmarking vs. SonarQube/Semgrep & Final Report.</li>
                            </ul>
                        </div>
                        <div class="card">
                            <h4>🛡️ Proactive Risk Mitigation Strategies</h4>
                            <div style="margin-bottom: 12px;">
                                <strong style="color: var(--accent-amber);">Risk:</strong> IDE typing latency during neural inference.<br>
                                <strong style="color: var(--accent-green);">Mitigation:</strong> Asynchronous background LSP workers; triggers only on save/idle debounce; maintainability executes in < 50ms.
                            </div>
                            <div>
                                <strong style="color: var(--accent-amber);">Risk:</strong> Inter-procedural taint path explosion.<br>
                                <strong style="color: var(--accent-green);">Mitigation:</strong> Bounded call graph traversal depth (d <= 3) prevents exponential runtime spikes.
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Slide 18 -->
            <div class="slide" data-index="18" data-time="15:00" data-script="To conclude, our team has established a balanced division of labor: Ongsa oversees the system architecture and neuro-symbolic security engine; Thanadon leads the maintainability algorithms, graph modeling, and LSP backend; and Brook leads the ChromaDB RAG pipeline, dataset curation, and VS Code user interface. CodeDEE demonstrates that developers do not have to choose between writing maintainable code and building secure applications. By unifying deterministic program graphs with local neural intelligence and multi-gate verification, CodeDEE makes secure, clean code the default path for modern web engineering. Thank you very much, and we now open the floor for your questions." data-tip="Finish strong and on time. Smile, thank the committee, and invite their questions.">
                <div class="slide-header">
                    <div>
                        <div class="slide-meta">Conclusion & Team Alignment</div>
                        <h2 class="slide-title">Summary & Division of Responsibilities</h2>
                    </div>
                    <div class="slide-num-pill">Slide 18 / 18</div>
                </div>
                <div class="slide-body">
                    <div class="grid-3" style="margin-bottom: 24px;">
                        <div class="card" style="text-align: center;">
                            <div style="font-size: 1.2rem; font-weight: 700; color: #fff;">Ongsa</div>
                            <div style="color: var(--accent-cyan); font-size: 0.85rem; margin-bottom: 10px;">Lead Architecture & Security</div>
                            <p style="font-size: 0.82rem; text-align: left;">• Overall System Architecture<br>• Neuro-Symbolic Security Engine<br>• Symbolic Taint Walker<br>• Multi-Gate Verifier Design</p>
                        </div>
                        <div class="card" style="text-align: center;">
                            <div style="font-size: 1.2rem; font-weight: 700; color: #fff;">Thanadon (Peem)</div>
                            <div style="color: var(--accent-blue); font-size: 0.85rem; margin-bottom: 10px;">Maintainability & Static Analysis</div>
                            <p style="font-size: 0.82rem; text-align: left;">• Tree-sitter CST Parsers<br>• Intermediate Graph Builders (CFG/DFG)<br>• 8 Maintainability Metric Calculators<br>• LSP Backend Server Adapter</p>
                        </div>
                        <div class="card" style="text-align: center;">
                            <div style="font-size: 1.2rem; font-weight: 700; color: #fff;">Brook</div>
                            <div style="color: var(--accent-green); font-size: 0.85rem; margin-bottom: 10px;">RAG & Machine Learning</div>
                            <p style="font-size: 0.82rem; text-align: left;">• ChromaDB Vector Store & Embeddings<br>• 5 Benchmark Datasets Curation<br>• Local Model Benchmarking (Ollama)<br>• VS Code UI & Diff Inspector</p>
                        </div>
                    </div>
                    <div style="text-align: center;">
                        <h3 style="color: var(--accent-cyan); font-size: 1.3rem;">Thank You for Your Guidance and Attention</h3>
                        <p style="color: var(--text-sub); margin-top: 6px;">We warmly invite questions, critiques, and feedback from the committee.</p>
                    </div>
                </div>
            </div>

            <!-- Slide 19 (Backup Q&A 1) -->
            <div class="slide" data-index="19" data-time="Q&A" data-script="Defense strategy for SonarQube/Snyk competition: Emphasize that SonarQube is passive and focuses on maintainability, while Snyk is purely security without automated repair. CodeDEE unifies both in one LSP engine and adds verified closed-loop patch generation." data-tip="Backup Slide: Use when examiners ask 'Why not just use SonarQube or Snyk?'">
                <div class="slide-header">
                    <div>
                        <div class="slide-meta">Appendix • Committee Defense Q&A</div>
                        <h2 class="slide-title">Q1: Why Not Just Use SonarQube or Snyk?</h2>
                    </div>
                    <div class="slide-num-pill">Backup 1</div>
                </div>
                <div class="slide-body">
                    <div class="grid-2">
                        <div class="card">
                            <h4>❌ Limitations of Existing Tools</h4>
                            <ul>
                                <li><strong>Fragmented Workflows:</strong> SonarQube checks maintainability; Snyk/Semgrep check security. They require separate configs, CI pipelines, and mental context-switching.</li>
                                <li><strong>Passive Diagnostic Scanners:</strong> They tell developers *what* is broken, but provide zero concrete code repairs tailored to the project's syntax.</li>
                                <li><strong>High False Alarm Rate:</strong> SAST lacks semantic understanding of custom sanitizers, leading to alert fatigue where warnings are ignored.</li>
                            </ul>
                        </div>
                        <div class="card" style="background: rgba(6, 182, 212, 0.08); border-color: var(--accent-cyan);">
                            <h4 style="color: var(--accent-cyan);">💡 CodeDEE's Distinct Architectural Edge</h4>
                            <ul>
                                <li><strong>Unified Quality & Security:</strong> Both dimensions evaluated over the same intermediate graph in a single pass.</li>
                                <li><strong>Active Program Repair:</strong> Generates automated patches validated by multi-gate verifiers before presentation.</li>
                                <li><strong>Semantic Taint Verification:</strong> RAG-assisted Neural Oracle understands custom sanitization functions, cutting false alarms.</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Slide 20 (Backup Q&A 2) -->
            <div class="slide" data-index="20" data-time="Q&A" data-script="Defense strategy for Neuro-Symbolic: Emphasize that pure LLMs hallucinate and leak code, while pure SAST is blind to custom logic. Symbolic taint tracking gives mathematical certainty; the LLM Oracle provides contextual judgment." data-tip="Backup Slide: Use when examiners ask 'Why combine symbolic graphs and LLMs?'">
                <div class="slide-header">
                    <div>
                        <div class="slide-meta">Appendix • Committee Defense Q&A</div>
                        <h2 class="slide-title">Q2: Why Neuro-Symbolic Instead of Pure LLM or Pure SAST?</h2>
                    </div>
                    <div class="slide-num-pill">Backup 2</div>
                </div>
                <div class="slide-body">
                    <div class="grid-2">
                        <div class="card">
                            <h4>⚠️ The Pitfalls of Single-Paradigm Approaches</h4>
                            <p><strong>Pure Symbolic SAST:</strong> Fast and deterministic, but rigid pattern rules cannot evaluate complex multi-file sanitization logic $\rightarrow$ high false positive rate.</p>
                            <p><strong>Pure Generative LLM:</strong> Context-aware, but suffers from stochastic hallucinations, context window exhaustion, high cloud latency, and IP leakage risks.</p>
                        </div>
                        <div class="card">
                            <h4>🤝 The CodeDEE Neuro-Symbolic Synergy</h4>
                            <p><strong>1. Deterministic Grounding:</strong> Symbolic Taint Walker and AST graphs provide mathematical ground truth for data flow.</p>
                            <p><strong>2. Contextual Program Slicing:</strong> Compresses 1,000 lines of code into a focused 20-line causal slice, keeping local SLM inference < 1.5s.</p>
                            <p><strong>3. Dense ChromaDB RAG:</strong> Enriches the LLM prompt with exact CWE remediation rules, eliminating stochastic hallucinations.</p>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Slide 21 (Backup Q&A 3) -->
            <div class="slide" data-index="21" data-time="Q&A" data-script="Defense strategy for Auto-Fix safety: Explain that the multi-gate verifier guarantees AST validity, security taint elimination, and maintainability non-regression. The bounded retry counter (k < 3) guarantees the loop terminates without hanging." data-tip="Backup Slide: Use when examiners ask 'What if the AI patch breaks code or enters an infinite loop?'">
                <div class="slide-header">
                    <div>
                        <div class="slide-meta">Appendix • Committee Defense Q&A</div>
                        <h2 class="slide-title">Q3: What If the AI Auto-Fix Breaks Code or Loops Forever?</h2>
                    </div>
                    <div class="slide-num-pill">Backup 3</div>
                </div>
                <div class="slide-body">
                    <div class="grid-2">
                        <div class="card">
                            <h4>🛡️ Multi-Gate Zero-Trust Verification</h4>
                            <ul>
                                <li><strong>Gate 1 (AST Syntax):</strong> Tree-sitter parses the patched code. Any syntax error immediately aborts and triggers retry.</li>
                                <li><strong>Gate 2 (Taint Elimination):</strong> Re-runs symbolic taint walker. If untrusted data still reaches the sink, the patch is rejected.</li>
                                <li><strong>Gate 3 (Maintainability Non-Regression):</strong> Confirms that CC, Cognitive, and SLOC did not degrade.</li>
                            </ul>
                        </div>
                        <div class="card">
                            <h4>🔄 Bounded Retry Loop ($k < 3$) & Human in the Loop</h4>
                            <ul>
                                <li><strong>Strict Iteration Bound:</strong> Retry count is capped at $k = 3$. If all 3 attempts fail, the system cleanly aborts auto-fix and presents a warning note.</li>
                                <li><strong>Zero Infinite Loops:</strong> Guaranteed finite execution time.</li>
                                <li><strong>Human Approval Required:</strong> CodeDEE never overwrites files automatically. The developer must inspect the unified diff and click 'Apply'.</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Slide 22 (Backup Q&A 4) -->
            <div class="slide" data-index="22" data-time="Q&A" data-script="Defense strategy for Base Severity vs Contextual Risk: Explain that Base Severity is the theoretical CVSS rating per CWE, used as a prompt anchor. Contextual Risk is evaluated by the Neural Oracle based on the actual code context to prevent alert fatigue." data-tip="Backup Slide: Use when examiners ask 'Why does severity appear in both Catalogue and LLM?'">
                <div class="slide-header">
                    <div>
                        <div class="slide-meta">Appendix • Committee Defense Q&A</div>
                        <h2 class="slide-title">Q4: Base Severity vs. Contextual Risk: Why Both?</h2>
                    </div>
                    <div class="slide-num-pill">Backup 4</div>
                </div>
                <div class="slide-body">
                    <div class="grid-2">
                        <div class="card">
                            <h4>🏛️ Symbolic Base Severity (Catalogue)</h4>
                            <ul>
                                <li><strong>Definition:</strong> Theoretical CVSS/NVD rating assigned to the CWE category (e.g., CWE-89 SQLi is High/Critical).</li>
                                <li><strong>Purpose 1 (Prompt Anchor):</strong> Injected into the LLM prompt to anchor the neural model and prevent it from underestimating serious flaws.</li>
                                <li><strong>Purpose 2 (Deterministic Fallback):</strong> Serves as the default severity if local LLM inference is offline or disabled.</li>
                            </ul>
                        </div>
                        <div class="card">
                            <h4>🎯 Neural Contextual Risk (LLM Oracle)</h4>
                            <ul>
                                <li><strong>Definition:</strong> Real-world risk level evaluated by the Neural Oracle considering the specific code context.</li>
                                <li><strong>Evaluates:</strong> Does the code have partial sanitization? Is the function internal-only? Is it reachable by external input?</li>
                                <li><strong>Developer Presentation:</strong> Displayed alongside Base Severity so developers know: <em>"Theoretically Critical, but Contextually Low Risk because an ORM parameterization wrapper is present."</em></li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Slide 23 (Backup Q&A 5) -->
            <div class="slide" data-index="23" data-time="Q&A" data-script="Defense strategy for Maintainability Thresholds: Cite McCabe (1976) for CC=10, SonarSource empirical research for Cognitive=15, and Hitz & Montazeri connected component graph analysis for LCOM4=1." data-tip="Backup Slide: Use when examiners ask 'How did you decide the threshold numbers?'">
                <div class="slide-header">
                    <div>
                        <div class="slide-meta">Appendix • Committee Defense Q&A</div>
                        <h2 class="slide-title">Q5: How Did You Derive the Maintainability Thresholds?</h2>
                    </div>
                    <div class="slide-num-pill">Backup 5</div>
                </div>
                <div class="slide-body">
                    <div class="grid-2">
                        <div class="card">
                            <h4>📖 Scientific Literature Foundations</h4>
                            <ul>
                                <li><strong>Cyclomatic Complexity (CC > 10):</strong> Established by Thomas McCabe (IEEE 1976). Empirical studies consistently demonstrate that functions with CC > 10 exhibit exponentially higher defect densities and require complex unit tests.</li>
                                <li><strong>Cognitive Complexity (> 15):</strong> Formulated by G. Ann Campbell (SonarSource). Calibrated against human cognitive working memory limits regarding nested control flows.</li>
                            </ul>
                        </div>
                        <div class="card">
                            <h4>📐 Graph Theory & Modularity Foundations</h4>
                            <ul>
                                <li><strong>LCOM4 (> 1):</strong> Derived from Hitz & Montazeri's graph theory formulation. Methods are vertices; shared instance variables are edges. An LCOM4 > 1 mathematically proves the presence of disjoint subgraphs, violating the Single Responsibility Principle.</li>
                                <li><strong>LOC (> 60 func / > 500 file):</strong> Standard empirical threshold from clean architecture literature preventing monolithic 'God Functions'.</li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Slide 24 (Backup Q&A 6) -->
            <div class="slide" data-index="24" data-time="Q&A" data-script="Defense strategy for LSP architecture: Explain that Language Server Protocol runs the engine out-of-process so the editor never freezes, allows backend reuse in JetBrains or NeoVim, and combines Python scientific libraries with a TypeScript extension." data-tip="Backup Slide: Use when examiners ask 'Why use LSP instead of writing everything directly in VS Code?'">
                <div class="slide-header">
                    <div>
                        <div class="slide-meta">Appendix • Committee Defense Q&A</div>
                        <h2 class="slide-title">Q6: Why Language Server Protocol (LSP) Over Direct Plugin?</h2>
                    </div>
                    <div class="slide-num-pill">Backup 6</div>
                </div>
                <div class="slide-body">
                    <div class="grid-2">
                        <div class="card">
                            <h4>⚡ 1. Process Isolation & Zero UI Freezing</h4>
                            <p>Running Tree-sitter graph generation and local SLM inference inside the VS Code Node.js extension thread would cause severe editor typing lag.</p>
                            <p>LSP runs the engine in a separate background process, communicating via asynchronous JSON-RPC. The editor remains completely fluid.</p>
                        </div>
                        <div class="card">
                            <h4>🌐 2. Multi-IDE Portability & Python Ecosystem</h4>
                            <p><strong>Universal Portability:</strong> LSP is an open standard. The same backend engine can power NeoVim, JetBrains (IntelliJ/PyCharm), and Sublime Text in the future.</p>
                            <p><strong>Ecosystem Synergy:</strong> The backend leverages Python's rich graph (NetworkX) and AI (ChromaDB, PyTorch/Ollama) libraries while the frontend remains a lightweight TypeScript client.</p>
                        </div>
                    </div>
                </div>
            </div>

        </div>

        <!-- Teleprompter / Speaker Notes Drawer -->
        <div class="teleprompter-drawer" id="teleprompterDrawer">
            <div class="drawer-header">
                <h3>🎙️ Spoken Teleprompter Script</h3>
                <span style="font-size: 0.8rem; color: var(--accent-cyan);" id="targetTimePill">Target: 0:40</span>
            </div>
            <div class="drawer-content">
                <div style="font-size: 0.78rem; text-transform: uppercase; color: var(--text-sub); font-weight: 700; margin-bottom: 8px;">Spoken Script (Read Confidently)</div>
                <div class="script-box" id="scriptContent">
                    Good morning, respected committee members and advisor Prof. Kookaip...
                </div>
                <div class="tip-box" id="tipContent">
                    💡 <strong>Delivery Tip:</strong> Open with a confident, measured tone.
                </div>
                <div style="margin-top: 20px; font-size: 0.75rem; color: #64748b;">
                    <strong>Keyboard Shortcuts:</strong><br>
                    • <code>←</code> / <code>→</code> or <code>Space</code> : Navigate Slides<br>
                    • <code>P</code> : Toggle Teleprompter<br>
                    • <code>F</code> : Toggle Fullscreen<br>
                    • <code>R</code> : Reset Timer
                </div>
            </div>
        </div>
    </div>

    <!-- Bottom Bar -->
    <div class="bottom-bar">
        <div>
            <button class="btn" onclick="prevSlide()">◀ Previous</button>
            <button class="btn" onclick="nextSlide()">Next ▶</button>
            <span style="margin-left: 14px;" id="slideIndicator">Slide 1 of 18 (Core Deck)</span>
        </div>

        <div class="progress-bar-container">
            <div class="progress-bar-fill" id="progressFill"></div>
        </div>

        <div>
            <span style="color: var(--accent-cyan); font-weight: 600;">Faculty of ICT, Mahidol University</span>
        </div>
    </div>

    <script>
        let currentSlide = 1;
        const totalSlides = document.querySelectorAll('.slide').length;
        const coreSlidesCount = 18;
        let timerSeconds = 15 * 60; // 15 minutes
        let timerInterval = null;
        let isTimerRunning = false;

        function updateSlide() {
            document.querySelectorAll('.slide').forEach(s => s.classList.remove('active'));
            const activeSlide = document.querySelector(`.slide[data-index="${currentSlide}"]`);
            if (activeSlide) {
                activeSlide.classList.add('active');
                
                // Update Drawer
                const script = activeSlide.getAttribute('data-script') || "No script provided.";
                const tip = activeSlide.getAttribute('data-tip') || "Keep pacing steady.";
                const targetTime = activeSlide.getAttribute('data-time') || "";
                
                document.getElementById('scriptContent').innerText = script;
                document.getElementById('tipContent').innerHTML = `💡 <strong>Delivery Tip:</strong> ${tip}`;
                document.getElementById('targetTimePill').innerText = targetTime ? `Target Time: ${targetTime}` : "Q&A Phase";
                
                // Update Progress and Indicator
                const isBackup = currentSlide > coreSlidesCount;
                document.getElementById('slideIndicator').innerText = isBackup 
                    ? `Slide ${currentSlide} of ${totalSlides} (Backup Q&A ${currentSlide - coreSlidesCount})`
                    : `Slide ${currentSlide} of ${coreSlidesCount} (Core Deck)`;
                
                const pct = (currentSlide / totalSlides) * 100;
                document.getElementById('progressFill').style.width = `${pct}%`;
            }
        }

        function nextSlide() {
            if (currentSlide < totalSlides) {
                currentSlide++;
                updateSlide();
            }
        }

        function prevSlide() {
            if (currentSlide > 1) {
                currentSlide--;
                updateSlide();
            }
        }

        function toggleTeleprompter() {
            const drawer = document.getElementById('teleprompterDrawer');
            const btn = document.getElementById('drawerToggleBtn');
            drawer.classList.toggle('collapsed');
            btn.classList.toggle('active');
        }

        function toggleFullscreen() {
            if (!document.fullscreenElement) {
                document.documentElement.requestFullscreen().catch(err => alert(err.message));
            } else {
                document.exitFullscreen();
            }
        }

        // Timer
        function formatTimer(sec) {
            const m = Math.floor(sec / 60);
            const s = sec % 60;
            return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
        }

        function updateTimerDisplay() {
            const display = document.getElementById('timer');
            display.innerText = formatTimer(timerSeconds);

            if (timerSeconds <= 60) {
                display.className = 'timer-display danger';
            } else if (timerSeconds <= 180) { // 3 mins left
                display.className = 'timer-display warning';
            } else {
                display.className = 'timer-display';
            }
        }

        function toggleTimer() {
            const btn = document.getElementById('timerToggleBtn');
            if (isTimerRunning) {
                clearInterval(timerInterval);
                isTimerRunning = false;
                btn.innerText = "▶ Resume";
                btn.classList.remove('active');
            } else {
                timerInterval = setInterval(() => {
                    if (timerSeconds > 0) {
                        timerSeconds--;
                        updateTimerDisplay();
                    } else {
                        clearInterval(timerInterval);
                        isTimerRunning = false;
                        btn.innerText = "Time Up!";
                    }
                }, 1000);
                isTimerRunning = true;
                btn.innerText = "⏸ Pause";
                btn.classList.add('active');
            }
        }

        function resetTimer() {
            clearInterval(timerInterval);
            isTimerRunning = false;
            timerSeconds = 15 * 60;
            updateTimerDisplay();
            const btn = document.getElementById('timerToggleBtn');
            btn.innerText = "▶ Start";
            btn.classList.remove('active');
        }

        // Keyboard Navigation
        document.addEventListener('keydown', (e) => {
            if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'PageDown') {
                e.preventDefault();
                nextSlide();
            } else if (e.key === 'ArrowLeft' || e.key === 'Backspace' || e.key === 'PageUp') {
                e.preventDefault();
                prevSlide();
            } else if (e.key.toLowerCase() === 'p') {
                e.preventDefault();
                toggleTeleprompter();
            } else if (e.key.toLowerCase() === 'f') {
                e.preventDefault();
                toggleFullscreen();
            } else if (e.key.toLowerCase() === 'r') {
                resetTimer();
            }
        });

        // Initial setup
        updateSlide();
        updateTimerDisplay();
    </script>
</body>
</html>
'''

output_path = 'visualizations/codedee_proposal_presentation_deck.html'
with open(output_path, 'w', encoding='utf-8') as f:
    f.write(html_content)

print(f"Successfully generated {output_path} (Size: {os.path.getsize(output_path)} bytes)")
