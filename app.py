from flask import Flask, render_template, request, jsonify, session
import os, secrets, glob, requests as http_requests, json
from ai_engine import rank_cases, parse_csv_to_cases, generate_case_summary_llm, _generate_fallback_summary

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

SAMPLES_DIR = os.path.join(os.path.dirname(__file__), 'samples')
os.makedirs(SAMPLES_DIR, exist_ok=True)


@app.route('/')
def index():
    return render_template('copilot.html')


def _load_local_samples():
    """Load all CSV files from the samples/ directory into a cases dict."""
    csv_files = sorted(glob.glob(os.path.join(SAMPLES_DIR, '*.csv')))
    all_cases = {}
    for filepath in csv_files:
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                text = f.read()
        except UnicodeDecodeError:
            with open(filepath, 'r', encoding='latin-1') as f:
                text = f.read()
        file_cases = parse_csv_to_cases(text)
        for case_id, variants in file_cases.items():
            label = case_id if case_id != "Sample A" else os.path.splitext(os.path.basename(filepath))[0]
            all_cases.setdefault(label, []).extend(variants)
    return all_cases


@app.route('/api/samples', methods=['GET'])
def list_samples():
    csv_files = sorted(glob.glob(os.path.join(SAMPLES_DIR, '*.csv')))
    samples = [{"name": os.path.basename(f), "size": os.path.getsize(f)} for f in csv_files]
    return jsonify({"success": True, "samples": samples})


@app.route('/api/upload', methods=['POST'])
def upload_samples():
    uploaded = request.files.getlist('csv_files')
    saved = []
    for f in uploaded:
        if f and f.filename and f.filename.lower().endswith(('.csv', '.tsv', '.txt')):
            safe_name = os.path.basename(f.filename)
            dest = os.path.join(SAMPLES_DIR, safe_name)
            f.save(dest)
            saved.append({"name": safe_name, "size": os.path.getsize(dest)})
    if not saved:
        return jsonify({"success": False, "error": "No valid CSV files uploaded."})
    return jsonify({"success": True, "saved": saved, "message": f"{len(saved)} file(s) added to /samples."})


@app.route('/api/remove_sample', methods=['POST'])
def remove_sample():
    data = request.get_json()
    name = os.path.basename(data.get('name', ''))
    filepath = os.path.join(SAMPLES_DIR, name)
    if os.path.exists(filepath):
        os.remove(filepath)
        return jsonify({"success": True, "message": f"Removed {name}."})
    return jsonify({"success": False, "error": f"File {name} not found."})


@app.route('/api/rank', methods=['POST'])
def rank_all():
    llm_provider = request.json.get('llm_provider', 'none') if request.is_json else 'none'
    all_cases = _load_local_samples()
    if not all_cases:
        return jsonify({"success": False, "error": "No CSV data in /samples folder."})
    return _rank_and_respond(all_cases, llm_provider)


@app.route('/api/analyze', methods=['POST'])
def analyze_vqs():
    data = request.get_json()
    from vqs_client import vqs
    auth = vqs.authenticate(data.get('username', ''), data.get('password', ''))
    if not auth.get('success'):
        return jsonify({"success": False, "error": f"Auth failed: {auth.get('error')}"})
    cases = {}
    for i, key in enumerate(data.get('dataset_keys', [])):
        key = key.strip()
        if not key: continue
        r = vqs.query_variants(dataset_key=key, columns=["*"], pagination={"offset": 0, "limit": 500})
        cases[f"Sample {chr(65 + i)}"] = r.get("data", []) if r.get("success") else []
    if not cases:
        return jsonify({"success": False, "error": "No data from VQS."})
    return _rank_and_respond(cases, data.get('llm_provider', 'none'))


# ─── LLM API Key ──────────────────────────────────────────────────────────

@app.route('/api/set_key', methods=['POST'])
def set_api_key():
    data = request.get_json()
    key = data.get('api_key', '').strip()
    provider = data.get('provider', 'anthropic')
    if not key:
        return jsonify({"success": False, "error": "No API key provided."})
    session['api_key'] = key
    session['llm_provider'] = provider
    return jsonify({"success": True, "message": f"{provider.capitalize()} API key saved for this session."})


# ─── PubMed Papers (no LLM) ───────────────────────────────────────────────

@app.route('/api/variant_papers', methods=['POST'])
def variant_papers():
    """Search PubMed for recent papers about a variant. No LLM involved."""
    data = request.get_json()
    gene = data.get('gene', '').strip()
    hgvs = data.get('hgvs', '').strip()

    if not gene:
        return jsonify({"success": False, "error": "Gene name required."})

    papers = _search_pubmed(gene, hgvs)

    return jsonify({
        "success": True,
        "gene": gene, "hgvs": hgvs,
        "papers": papers,
    })


def _search_pubmed(gene, hgvs='', max_results=8):
    """Search PubMed E-utilities for recent papers about a gene/variant."""
    terms = [gene]
    if hgvs:
        terms.append(hgvs)
    terms.append('variant')
    query = ' '.join(terms)

    try:
        search_url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi'
        sr = http_requests.get(search_url, params={
            'db': 'pubmed', 'term': query, 'retmax': max_results,
            'sort': 'date', 'retmode': 'json'
        }, timeout=10)
        sr.raise_for_status()
        ids = sr.json().get('esearchresult', {}).get('idlist', [])

        if not ids:
            sr = http_requests.get(search_url, params={
                'db': 'pubmed', 'term': f'{gene} variant pathogenic therapy',
                'retmax': max_results, 'sort': 'date', 'retmode': 'json'
            }, timeout=10)
            ids = sr.json().get('esearchresult', {}).get('idlist', [])

        if not ids:
            return []

        fetch_url = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi'
        fr = http_requests.get(fetch_url, params={
            'db': 'pubmed', 'id': ','.join(ids), 'retmode': 'json'
        }, timeout=10)
        fr.raise_for_status()
        result = fr.json().get('result', {})

        papers = []
        for pid in ids:
            p = result.get(pid, {})
            if not p or 'title' not in p:
                continue
            authors = ', '.join([a.get('name', '') for a in p.get('authors', [])[:3]])
            if len(p.get('authors', [])) > 3:
                authors += ' et al.'
            papers.append({
                'pmid': pid,
                'title': p.get('title', ''),
                'authors': authors,
                'journal': p.get('fulljournalname', p.get('source', '')),
                'date': p.get('pubdate', ''),
                'url': f'https://pubmed.ncbi.nlm.nih.gov/{pid}/'
            })

        return papers

    except Exception as e:
        print(f"PubMed search error: {e}")
        return []


# ─── Rank & Respond ───────────────────────────────────────────────────────

def _rank_and_respond(cases, llm_provider):
    ranked = rank_cases(cases)
    for c in ranked:
        # Always generate deterministic summary
        c['summary'] = _generate_fallback_summary(c)
        # Try to add LLM clinical summary on top
        api_key = session.get('api_key', '')
        provider = session.get('llm_provider', llm_provider)
        if provider and provider != 'none' and api_key:
            llm_text = generate_case_summary_llm(c, provider, api_key)
            if llm_text:
                c['llm_summary'] = llm_text  # Separate field for LLM text
    return jsonify({"success": True, "ranked_cases": ranked})


if __name__ == '__main__':
    app.run(debug=True, port=5001)
