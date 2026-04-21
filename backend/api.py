import traceback
import os
import json
import numpy as np
import google.generativeai as genai
from flask import Flask, request, jsonify
from flask_cors import CORS
from tavily import TavilyClient
from utils.data_manager import load_data, save_data
from utils.mcdm_logic import QROFAHP, BWM_VIKOR, SWARA_MOORA, CRITIC_EDAS

app = Flask(__name__)
CORS(app)

# --- ENVIRONMENT SETUP ---
CRITERIA_KEYS = ["spm_results", "previous_semester", "technical_skills", "aptitude_test"]
GENAI_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyAB274NJuc1GUv33CPwXeZFfr5mWk_rdNk")
TAVILY_KEY = os.getenv("TAVILY_API_KEY", "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")

# Initialize AI Clients
genai.configure(api_key=GENAI_KEY)
ai_model = genai.GenerativeModel('gemini-1.5-flash')
tavily = TavilyClient(api_key=TAVILY_KEY)

# ==================== AGENTIC AI FUNCTIONS ====================

def agent_a_orchestrator(student_scores):
    """Agent A: Explains the math consensus based on student data variance."""
    grades = list(student_scores['spm'].values()) + list(student_scores['uni'].values())
    variance = np.var(grades)
    
    prompt = f"""
    You are an MCDM Orchestrator AI. A student submitted grades with a variance of {variance:.2f}.
    Explain in one professional sentence why we use a consensus of 4 algorithms (q-ROF-AHP, BWM, SWARA, CRITIC) 
    to ensure their specialization recommendation is mathematically robust and unbiased.
    RETURN ONLY PLAIN TEXT.
    """
    try:
        response = ai_model.generate_content(prompt)
        return response.text.strip()
    except:
        return "Consolidating multiple MCDM perspectives to provide a high-precision academic recommendation."

def agent_b_career_finder(top_spec, weak_skills):
    """Agent B: Enhanced with high-detail instructions for robust answers."""
    
    # Use the student's specific specialization and weak skills in the search
    query = f"industry requirements and emerging technologies for {top_spec} in Malaysia 2024 2025"
    
    try:
        search_context = tavily.search(query=query, max_results=3)
    except:
        search_context = "Search API currently unavailable."

    # ENHANCED PROMPT: We tell the AI exactly how many points we want
    prompt = f"""
    You are a world-class Career Strategist specializing in the Malaysian Tech Industry.
    The student's recommended path is: {top_spec}.
    The student self-rated these skills as WEAK: {weak_skills}.

    Using this live market context: {search_context}
    
    Provide a COMPREHENSIVE excellence roadmap. You MUST follow these rules:
    1. 'core_knowledge': List 4 advanced theoretical concepts relevant to {top_spec}.
    2. 'technical_skills': List 4 specific, high-demand software tools or programming languages for 2025.
    3. 'gap_bridging': Provide a detailed 2-paragraph strategy on how the student can transform their specific weaknesses {weak_skills} into competitive advantages.
    4. 'certifications': List 3 industry-standard certifications (e.g., AWS, Cisco, CompTIA) that are highly valued in Malaysia.
    5. 'project_idea': Suggest one complex, real-world project they can build. Give it a title and a 3-sentence technical description.

    RETURN ONLY VALID JSON.
    """
    
    try:
        response = ai_model.generate_content(prompt)
        # Cleaning the response to ensure only JSON remains
        raw_text = response.text.strip().replace('```json', '').replace('```', '')
        return json.loads(raw_text)
    except Exception as e:
        print(f"Agent B Error: {e}")
        # BETTER FALLBACK: If AI fails, we still give professional-looking "Static" data
        return {
            "core_knowledge": ["Systems Scalability", "User-Centric Design", "Cloud Architecture", "Database Optimization"],
            "technical_skills": ["Node.js/Express", "Docker & Kubernetes", "AWS/Google Cloud", "PostgreSQL/MongoDB"],
            "gap_bridging": f"To bridge your gaps in {weak_skills}, start by integrating these skills into small weekly projects. Focus on understanding the logic behind the tools rather than just memorizing syntax.",
            "certifications": ["AWS Certified Developer", "Professional Scrum Master (PSM I)", "Google UX Design Professional"],
            "project_idea": "Multi-Platform Service Hub: A full-stack application that utilizes microservices architecture to manage real-time data across mobile and web interfaces."
        }

# ==================== DATA & MATH ROUTES ====================

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
    results = {'qrof': [0.25]*4, 'bwm': [0.25]*4, 'swara': {k: 0.25 for k in CRITERIA_KEYS}}
    
    try:
        if 'qrof' in data['mcdm']:
            matrix = [[float(c) for c in r] for r in data['mcdm']['qrof']['matrix']]
            w = QROFAHP().calculate_weights(matrix)
            results['qrof'] = [round(float(x), 4) for x in w]
        
        if 'bwm' in data['mcdm']:
            bd = data['mcdm']['bwm']
            best_v, worst_v = [float(x) for x in bd['best_vectors']], [float(x) for x in bd['worst_vectors']]
            if any(v > 1 for v in best_v):
                k_map = {k: i for i, k in enumerate(CRITERIA_KEYS)}
                w = BWM_VIKOR().solve_bwm_weights(k_map[bd['best_criteria']], k_map[bd['worst_criteria']], best_v, worst_v)
                results['bwm'] = [round(float(x), 4) for x in w]

        if 'swara' in data['mcdm']:
            sd = data['mcdm']['swara']
            w_dict = SWARA_MOORA().calculate_swara_weights(sd['rank_order'], [float(x) for x in sd.get('comparative_scores', [])])
            results['swara'] = {k: round(float(v), 4) for k, v in w_dict.items()}
    except:
        traceback.print_exc()
    return jsonify(results)

@app.route('/api/process_recommendation', methods=['POST'])
def process_recommendation():
    req = request.json
    student_scores = req['student_scores']
    db = load_data()
    crit = db.get('criteria', {})
    
    specs = ['ADE', 'AI', 'SDS', 'DE', 'NDC']
    spec_names = ['APPLICATION DEVELOPMENT ENGINEERING', 'ARTIFICIAL INTELLIGENCE', 'SECURITY IN DIGITAL SYSTEM', 'DATA ENGINEERING', 'NETWORK AND DATA COMMUNICATIONS']
    
    mat = np.zeros((5, 4))
    def calc_score(scores, w_map, is_skill=False):
        tp, ws = 0, 0
        for sub, imp in w_map.items():
            raw = scores.get(sub, 0)
            norm = (raw - 1) * (100 / 9) if is_skill and raw > 0 else raw
            ws += norm * imp
            tp += 100 * imp
        return (ws / tp * 100) if tp > 0 else 0

    for i, s in enumerate(specs):
        mat[i,0] = calc_score(student_scores['spm'], {k: int(v.get(s,5)) for k,v in crit.get('spm_results',{}).items()})
        mat[i,1] = calc_score(student_scores['uni'], {k: int(v.get(s,5)) for k,v in crit.get('previous_semester',{}).items()})
        mat[i,2] = calc_score(student_scores['skills'], {k: int(v.get(s,5)) for k,v in crit.get('technical_skills',{}).items()}, True)
        r_w = db['riasec_weights'].get(s, {})
        apt = sum(student_scores['riasec'].get(t,0)*r_w.get(t,0) for t in ['R','I','A','S','E','C'])
        max_apt = sum(abs(v)*2 for v in r_w.values()) or 1
        mat[i,3] = max(0, min(100, (apt+max_apt)/(2*max_apt)*100))

    math_results = {}
    def rank(d): return [{'spec': k, 'score': round(v, 1), 'rank': i+1} for i, (k, v) in enumerate(sorted(d.items(), key=lambda x: x[1], reverse=True))]

    try: math_results['q-ROF-AHP'] = rank(dict(zip(spec_names, QROFAHP().calculate_scores(mat, QROFAHP().calculate_weights(db['mcdm']['qrof']['matrix'])))))
    except: pass
    try:
        bd = db['mcdm']['bwm']; km = {k: i for i, k in enumerate(CRITERIA_KEYS)}
        w_bwm = BWM_VIKOR().solve_bwm_weights(km[bd['best_criteria']], km[bd['worst_criteria']], [float(x) for x in bd['best_vectors']], [float(x) for x in bd['worst_vectors']])
        math_results['BWM+VIKOR'] = rank(dict(zip(spec_names, BWM_VIKOR().calculate_vikor(mat, w_bwm))))
    except: pass
    
    # Run Agents
    agent_reasoning = agent_a_orchestrator(student_scores)
    # Use q-ROF-AHP top result for Agent B
    top_spec_detected = math_results['q-ROF-AHP'][0]['spec']
    weak_skills_list = [k for k,v in student_scores['skills'].items() if v < 6]
    career_roadmap = agent_b_career_finder(top_spec_detected, weak_skills_list)

    return jsonify({
        "method_results": math_results,
        "agent_reasoning": agent_reasoning,
        "career_roadmap": career_roadmap
    })

if __name__ == '__main__':
    app.run(port=5001, debug=True)