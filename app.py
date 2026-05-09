from flask import Flask, render_template, request, jsonify, session
import os, secrets, glob
from ai_engine import rank_cases, parse_csv_to_cases, generate_case_summary_llm, _generate_fallback_summary
from vqs_client import vqs

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
    """List available sample CSV files."""
    csv_files = sorted(glob.glob(os.path.join(SAMPLES_DIR, '*.csv')))
    samples = [{"name": os.path.basename(f), "size": os.path.getsize(f)} for f in csv_files]
    return jsonify({"success": True, "samples": samples})


@app.route('/api/upload', methods=['POST'])
def upload_samples():
    """Upload CSV files and save them to the /samples directory."""
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
    """Remove a sample CSV file from /samples."""
    data = request.get_json()
    name = os.path.basename(data.get('name', ''))
    filepath = os.path.join(SAMPLES_DIR, name)
    if os.path.exists(filepath):
        os.remove(filepath)
        return jsonify({"success": True, "message": f"Removed {name}."})
    return jsonify({"success": False, "error": f"File {name} not found."})


@app.route('/api/rank', methods=['POST'])
def rank_all():
    """Rank all CSV files currently in /samples."""
    llm_provider = request.json.get('llm_provider', 'none') if request.is_json else 'none'
    all_cases = _load_local_samples()
    if not all_cases:
        return jsonify({"success": False, "error": "No CSV data in /samples folder."})
    return _rank_and_respond(all_cases, llm_provider)


@app.route('/api/analyze', methods=['POST'])
def analyze_vqs():
    data = request.get_json()
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


def _rank_and_respond(cases, llm_provider):
    ranked = rank_cases(cases)
    for c in ranked:
        c['summary'] = (generate_case_summary_llm(c, llm_provider, session.get('api_key', ''))
                        if llm_provider != 'none' else _generate_fallback_summary(c))
    return jsonify({"success": True, "ranked_cases": ranked})


if __name__ == '__main__':
    app.run(debug=True, port=5001)
