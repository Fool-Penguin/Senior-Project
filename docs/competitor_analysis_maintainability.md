# Competitor Analysis: Maintainability & Code Quality

This document contains the competitor analysis for **CodeDEE** focusing on **Maintainability, Code Quality, and Architecture Metrics**, comparing it against **SonarQube for IDE**, **ESLint**, **CodeScene**, and **Pylint**.

---

## 1. Tool Characteristics Comparison Table

| Tool | Main Focus | Languages | Analysis Scope | Levels Analysed | How It Reads the Code | Exportable Report | Automatic Fixes | Fixes Use Project Context |
| :--- | :--- | :--- | :--- | :--- | :--- | :---: | :--- | :---: |
| **SonarQube for IDE** | Maintainability, Reliability and Security | Python, JS/TS, Java, C#, C/C++, Go, PHP, HTML, XML, IaC and more | Files or Whole Project | Function, class (Python), file | AST: SonarSource's own Python parser; ESLint-based for JS/TS | ❌ | Rule-based quick fixes (local); AI CodeFix (paid server only) | ❌ |
| **ESLint** | Code quality and style | JS/TS (other languages through plugins) | Files or whole project (CLI) | Function, file | AST (ESTree) | ✅: JSON | Rule-based fix | ❌ |
| **CodeScene** | Maintainability (Code Health) | 31 languages | Whole project, plus git history | Function, class/file, project | Not documented | ✅: JSON (CLI) | AI refactoring with ACE | ❌ |
| **Pylint** | Code quality and style | Python only | Files or whole project (CLI) | Function, class, file | AST (astroid) | ✅: JSON and text | ❌ | — |
| **CodeDEE (Our Work)** | **Maintainability and security** | **Python, JS, TS** | **Files or whole project** | **Function, file, project** | **Tree-sitter plus taint graph** | **❌** | **Local LLM suggestion & fix** | **✅** |

---

## 2. Maintainability & Code Quality Metrics Comparison Table

| Tool | Cyclomatic Complexity | Cognitive Complexity | SLOC | LOC | Code Duplication | Coupling | Cohesion | Nesting Depth | Parameters | Comment Density | DIT | Methods / Class |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **SonarQube for IDE** | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| **ESLint** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| **CodeScene** | ✅ | ❌ | ✅ | ❌ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Pylint** | ✅ | ❌ | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **CodeDEE (Our Work)** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |

