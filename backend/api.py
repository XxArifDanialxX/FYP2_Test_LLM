import os
import json
import traceback
import numpy as np
from flask import Flask, request, jsonify
from flask_cors import CORS
from google import genai  # 2026 SDK Standard
from tavily import TavilyClient
from utils.data_manager import load_data, save_data
from utils.mcdm_logic import QROFAHP, BWM_VIKOR, SWARA_MOORA, CRITIC_EDAS

app = Flask(__name__)
CORS(app)

# ==================== CONFIGURATION ====================
CRITERIA_KEYS = ["spm_results", "previous_semester", "technical_skills", "aptitude_test"]
SPEC_NAMES = [
    'APPLICATION DEVELOPMENT ENGINEERING', 
    'ARTIFICIAL INTELLIGENCE', 
    'SECURITY IN DIGITAL SYSTEM', 
    'DATA ENGINEERING', 
    'NETWORK AND DATA COMMUNICATIONS'
]

# API Keys (Use Environment Variables on Render)
GENAI_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyCqeyYjlt23YToWXe36mZh1hWoe1ySCDcQ")
TAVILY_KEY = os.getenv("TAVILY_API_KEY", "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")

client = genai.Client(api_key=GENAI_KEY)
tavily = TavilyClient(api_key=TAVILY_KEY)
MODEL_ID = "gemini-2.0-flash" 

# ==================== AGENT A: THE ORCHESTRATOR ====================

def get_agent_orchestration_decision(student_scores):
    """
    AGENT A: Statistical Analyst Agent.
    Evaluates data quality and decides which MCDM engine to trust.
    """
    all_grades = list(student_scores['spm'].values()) + list(student_scores['uni'].values())
    variance = np.var(all_grades) if all_grades else 0
    
    prompt = f"""
    You are the MCDM Orchestrator AI. The student's academic profile has a variance of {variance:.2f}.
    
    TASK: Distribute 1.0 Trust Weight points across 4 mathematical models based on these rules:
    1. If Variance is HIGH (>30), student data is inconsistent. Prioritize 'critic' (Objective math).
    2. If Variance is LOW (<10), student data is consistent. Prioritize 'qrof' and 'swara' (Subjective expert math).
    
    RETURN ONLY RAW JSON:
    {{
        "reasoning": "A 1-sentence technical explanation of this specific weighting.",
        "trust_weights": {{"qrof": 0.25, "bwm": 0.25, "swara": 0.25, "critic": 0.25}}
    }}
    """
    try:
        response = client.models.generate_content(model=MODEL_ID, contents=prompt)
        text = response.text.strip()
        json_str = text[text.find('{'):text.rfind('}')+1]
        return json.loads(json_str)
    except:
        return {
            "reasoning": "Using a balanced consensus model as the AI reasoning engine is currently at capacity.",
            "trust_weights": {"qrof": 0.25, "bwm": 0.25, "swara": 0.25, "critic": 0.25}
        }

# ==================== AGENT B: EXCELLENCE ROADMAP ====================

def get_career_insight(top_spec, weak_skills):
    """
    AGENT B: Industry Researcher Agent.
    Searches live Malaysian trends 2026 and creates a tailored skill roadmap.
    """
    try:
        search_query = f"Malaysian industry demand and required skills for {top_spec} roles in 2026"
        search_result = tavily.search(query=search_query, max_results=3)
        context = search_result['results']
    except:
        context = "Market data offline."

    prompt = f"""
    Role: Career Strategist. Target: {top_spec}. Student Weaknesses: {weak_skills}. Context: {context}
    
    Generate a 2026-Ready Excellence Roadmap in JSON:
    {{
        "core_knowledge": ["4 specific theoretical concepts"],
        "technical_skills": ["4 modern software tools/languages"],
        "gap_bridging": "A detailed 2-paragraph strategy to fix {weak_skills} for {top_spec}.",
        "certifications": ["3 specific industry certificates valued in SE Asia"],
        "project_idea": "A technical title and 2-sentence technical description."
    }}
    RETURN ONLY JSON.
    """
    try:
        response = client.models.generate_content(model=MODEL_ID, contents=prompt)
        text = response.text.strip()
        return json.loads(text[text.find('{'):text.rfind('}')+1])
    except:
        return {
            "core_knowledge": [f"Advanced {top_spec} Foundations", "Systems Architecture", "Algorithmic Efficiency", "Data Ethics"],
            "technical_skills": ["Python / C++", "Cloud Infrastructure (AWS/Azure)", "SQL & NoSQL", "Git/CI-CD"],
            "gap_bridging": f"To overcome your low scores in {weak_skills}, integrate these concepts into daily coding exercises specifically tailored for {top_spec} applications.",
            "certifications": [f"Professional {top_spec} Cert", "Cloud Solutions Architect", "Cybersecurity Fundamentals"],
            "project_idea": f"Comprehensive {top_spec} Prototype: Build an automated system that solves a real-world problem using the latest frameworks."
        }

# ==================== MATH NORMALIZATION ====================

def calc_weighted_score(student_scores, weight_map, is_skill=False):
    total_possible = 0
    weighted_score = 0
    for sub, imp in weight_map.items():
        raw = student_scores.get(sub, 0)
        # Normalize skill ratings 1-10 to 100%
        normalized = (raw - 1) * (100 / 9) if is_skill and raw > 0 else raw
        weighted_score += normalized * imp
        total_possible += 100 * imp
    return (weighted_score / total_possible * 100) if total_possible > 0 else 0

# ==================== CORE ROUTES ====================

@app.route('/api/get_data', methods=['GET'])
def get_data():
    return jsonify(load_data())

@app.route('/api/save_data', methods=['POST'])
def save():
    save_data(request.json)
    return jsonify({"status": "success"})

@app.route('/api/calculate_weights', methods=['GET'])
def calc_weights():
    data = load_data()
    res = {'qrof': [0.25]*4, 'bwm': [0.25]*4, 'swara': {k: 0.25 for k in CRITERIA_KEYS}}
    try:
        if 'qrof' in data['mcdm']:
            m = [[float(c) for c in r] for r in data['mcdm']['qrof']['matrix']]
            res['qrof'] = [round(float(x), 4) for x in QROFAHP().calculate_weights(m)]
        if 'bwm' in data['mcdm']:
            bd = data['mcdm']['bwm']; km = {k: i for i, k in enumerate(CRITERIA_KEYS)}
            w = BWM_VIKOR().solve_bwm_weights(km[bd['best_criteria']], km[bd['worst_criteria']], [float(x) for x in bd['best_vectors']], [float(x) for x in bd['worst_vectors']])
            res['bwm'] = [round(float(x), 4) for x in w]
        if 'swara' in data['mcdm']:
            sd = data['mcdm']['swara']
            w_d = SWARA_MOORA().calculate_swara_weights(sd['rank_order'], [float(x) for x in sd.get('comparative_scores', [])])
            res['swara'] = {k: round(float(v), 4) for k, v in w_d.items()}
    except: pass
    return jsonify(res)

@app.route('/api/process_recommendation', methods=['POST'])
def process_recommendation():
    try:
        req = request.json
        scores = req['student_scores']
        db = load_data()
        crit_db = db.get('criteria', {})

        # 1. AGENT A DECISION: Weights algorithms based on student variance
        orchestration = get_agent_orchestration_decision(scores)
        tw = orchestration['trust_weights']

        # 2. BUILD MATRIX (5 Specs x 4 Criteria)
        mat = np.zeros((5, 4))
        short_keys = ['ADE', 'AI', 'SDS', 'DE', 'NDC']
        for i, s in enumerate(short_keys):
            mat[i,0] = calc_weighted_score(scores['spm'], {k: int(v.get(s,5)) for k,v in crit_db.get('spm_results',{}).items()})
            mat[i,1] = calc_weighted_score(scores['uni'], {k: int(v.get(s,5)) for k,v in crit_db.get('previous_semester',{}).items()})
            mat[i,2] = calc_weighted_score(scores['skills'], {k: int(v.get(s,5)) for k,v in crit_db.get('technical_skills',{}).items()}, True)
            r_w = db['riasec_weights'].get(s, {})
            apt = sum(scores['riasec'].get(t,0)*r_w.get(t,0) for t in ['R','I','A','S','E','C'])
            max_apt = sum(abs(v)*2 for v in r_w.values()) or 1
            mat[i,3] = max(0, min(100, (apt+max_apt)/(2*max_apt)*100))

        # 3. RUN ENGINES
        # q-ROF-AHP
        q_w = QROFAHP().calculate_weights(db['mcdm']['qrof']['matrix'])
        q_sc = QROFAHP().calculate_scores(mat, q_w)
        # BWM
        bd = db['mcdm']['bwm']; km = {k: i for i, k in enumerate(CRITERIA_KEYS)}
        b_w = BWM_VIKOR().solve_bwm_weights(km[bd['best_criteria']], km[bd['worst_criteria']], [float(x) for x in bd['best_vectors']], [float(x) for x in bd['worst_vectors']])
        b_sc = BWM_VIKOR().calculate_vikor(mat, b_w)
        # SWARA
        sd = db['mcdm']['swara']; sw_eng = SWARA_MOORA()
        sw_d = sw_eng.calculate_swara_weights(sd['rank_order'], [float(x) for x in sd.get('comparative_scores', [])])
        sw_w = np.array([sw_d.get(k, 0.25) for k in CRITERIA_KEYS])
        sw_sc = sw_eng.calculate_moora(mat, sw_w)
        # CRITIC
        cr_sc, _ = CRITIC_EDAS().execute(mat)

        # 4. AGENTIC AGGREGATION
        final_scores = {}
        for i, name in enumerate(SPEC_NAMES):
            weighted = (q_sc[i]*tw['qrof']) + (b_sc[i]*tw['bwm']) + (sw_sc[i]*tw['swara']) + (cr_sc[i]*tw['critic'])
            final_scores[name] = round(float(weighted), 1)

        consensus = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)
        consensus_list = [{"spec": k, "score": v, "rank": i+1} for i, (k, v) in enumerate(consensus)]

        # 5. AGENT B RESEARCH
        weak_list = [k.replace('_', ' ') for k, v in scores['skills'].items() if v < 6]
        roadmap = get_career_insight(consensus_list[0]['spec'], weak_list)

        # 6. PACKAGE FOR UI
        def pack(sc):
            d = {SPEC_NAMES[i]: sc[i] for i in range(5)}
            return [{"spec": k, "score": round(v,1), "rank": i+1} for i, (k, v) in enumerate(sorted(d.items(), key=lambda x: x[1], reverse=True))]

        return jsonify({
            "consensus": consensus_list,
            "method_results": {
                "q-ROF-AHP": pack(q_sc), "BWM+VIKOR": pack(b_sc), 
                "SWARA+MOORA": pack(sw_sc), "CRITIC+EDAS": pack(cr_sc)
            },
            "agent_reasoning": orchestration['reasoning'],
            "career_roadmap": roadmap
        })
    except Exception:
        traceback.print_exc()
        return jsonify({"error": "Computation failure"}), 500

if __name__ == '__main__':
    app.run(port=5001, debug=True)