# Policy Compliance Validator

This project demonstrates a system for validating internal Policies and Procedures (P&Ps) against regulatory requirements.

---

## Problem

Compliance analysts must manually interpret questionnaires and evolving Policy Guides, mapping questions and obligations to supporting language across hundreds of lengthy policy documents, a slow and error-prone process where semantic mismatches and missed requirements can lead to regulatory findings.

## 🚀 Solution Overview

### 1. Parse questionnaire
Upload a regulatory questionnaire and extract questionnaire items (individual compliance checks).

### 2. Parse policy guide
Upload a policy guide and extract obligations, normalized into questionnaire items.

### 3. Validate against P&Ps
Each questionnaire item is automatically validated against a corpus of P&P documents.

For each item, the system returns:
- Conclusion: supported / conflicted / not supported  
- Confidence: 0 to 1  
- Rationale: short explanation  
- Supporting citations  
- Conflicting citations  

---

## 🧠 Key concept: Questionnaire items

A questionnaire item is a single compliance check, for example:

“Does the P&P state that retrospective review requests will be responded to within 14 days?”

These can come from:
- a real questionnaire (parsed directly)
- a policy guide (obligations converted into questions)

---

## 🏗️ Architecture

Questionnaire or Policy Guide

↓ (LLM extraction)

Questionnaire Items

↓ (retrieval + LLM validation)

Validation Results

---

## ⚙️ Setup

### 1. Clone repo

```git clone https://github.com/tristenallgaier2023/readily-module.git```

```cd readily-module```

### 2. Create virtual env

```python -m venv .venv```

```source .venv/bin/activate```     # Mac/Linux

```.venv\Scripts\activate```        # Windows

### 3. Install dependencies

```pip install -r requirements.txt```

---

## 🔑 API key setup

Create:

.streamlit/secrets.toml

OPENAI_API_KEY = "your_key_here"

---

## ▶️ Run locally

```streamlit run app.py```

---

## ☁️ Deploy (Streamlit Cloud)

1. Push repo to GitHub  
2. Go to Streamlit Community Cloud  
3. Create new app  
4. Set entrypoint: app.py  
5. Add secret in UI: OPENAI_API_KEY  

---

## 🧪 Sample data

The repo includes synthetic sample data to demonstrate:
- supported cases  
- not supported cases  
- conflicted cases  

This keeps the demo fast, low cost, and easy to verify.

---

## ⚠️ Assumptions

- The prompt references “a couple of real APLs,” but none were included in the dataset or described in the customer use case. This solution therefore uses policy guides and questionnaires as the only regulatory inputs.  
- Recommended actions are excluded because the use cases are “answering regulatory questionnaires” and “flagging what needs to be written or updated,” not prescribing specific changes.  
- Extracted obligations are treated as functionally equivalent to questionnaire items. Obligations are normalized into questions so they can be used as inputs to the P&P validation flow.  

---

## 🔮 Future extensions

- Automated test coverage (unit tests, integration tests, CI/CD pipeline)  
- Monitoring (logging, alerting, dashboards)  
- Parallel processing to support larger datasets and reduce latency  
- Integration with external P&P sources (for example Google Drive)  
- Automatic detection of input type (questionnaire vs policy guide) to remove the need for user selection
- Improve evaluation and confidence scoring to better surface edge cases and contradictions  

---

## 🧾 Summary

This project demonstrates how to:
- convert unstructured regulatory text into structured checks  
- map those checks to internal policies  
- automatically determine compliance with supporting evidence  
