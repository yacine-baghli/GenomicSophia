from flask import Flask, render_template, request, jsonify, session
import os, secrets
from ai_engine import rank_cases, parse_csv_to_cases, generate_case_summary_llm, _generate_fallback_summary
from vqs_client import vqs

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)

@app.route('/')
def index():
    return render_template('copilot.html')

@app.route('/api/analyze', methods=['POST'])
def analyze_vqs():
    data = request.get_json()
    auth = vqs.authenticate(data.get('username',''), data.get('password',''))
    if not auth.get('success'):
        return jsonify({"success": False, "error": f"Auth failed: {auth.get('error')}"})
    cases = {}
    for i, key in enumerate(data.get('dataset_keys', [])):
        key = key.strip()
        if not key: continue
        r = vqs.query_variants(dataset_key=key, columns=["*"], pagination={"offset":0,"limit":500})
        cases[f"Sample {chr(65+i)}"] = r.get("data", []) if r.get("success") else []
    if not cases:
        return jsonify({"success": False, "error": "No data from VQS."})
    return _rank_and_respond(cases, data.get('llm_provider','none'))

@app.route('/api/csv', methods=['POST'])
def analyze_csv():
    if 'csv_file' not in request.files or request.files['csv_file'].filename == '':
        return jsonify({"success": False, "error": "No CSV file."})
    try:
        text = request.files['csv_file'].read().decode('utf-8')
    except UnicodeDecodeError:
        request.files['csv_file'].seek(0)
        text = request.files['csv_file'].read().decode('latin-1')
    cases = parse_csv_to_cases(text)
    if not cases:
        return jsonify({"success": False, "error": "No data in CSV."})
    return _rank_and_respond(cases, request.form.get('llm_provider','none'))

def _rank_and_respond(cases, llm_provider):
    ranked = rank_cases(cases)
    for c in ranked:
        c['summary'] = (generate_case_summary_llm(c, llm_provider, session.get('api_key',''))
                        if llm_provider != 'none' else _generate_fallback_summary(c))
    return jsonify({"success": True, "ranked_cases": ranked})

if __name__ == '__main__':
    app.run(debug=True, port=5001)
