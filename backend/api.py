import traceback
from flask import Flask, request, jsonify
from flask_cors import CORS
import numpy as np
from utils.data_manager import load_data, save_data
from utils.mcdm_logic import QROFAHP, BWM_VIKOR, SWARA_MOORA, CRITIC_EDAS

app = Flask(__name__)
CORS(app)

# Constants used for mapping JSON keys to indices
CRITERIA_KEYS = ["spm_results", "previous_semester", "technical_skills", "aptitude_test"]

# ==================== 1. DATA ACCESS ROUTES ====================

@app.route('/api/get_data', methods=['GET'])
def get_data():
    """Returns the entire expert_data.json content"""
    return jsonify(load_data())

@app.route('/api/save_data', methods=['POST'])
def save():
    """Saves updated configuration from Frontend to expert_data.json"""
    data = request.json
    save_data(data)
    return jsonify({"status": "success"})

# ==================== 2. WEIGHT CALCULATION ROUTE ====================

@app.route('/api/calculate_weights', methods=['GET'])
def calc_weights():
    """Calculates the 4 main criteria weights using QROF, BWM, and SWARA"""
    data = load_data()
    
    # Default fallbacks (0.25 each)
    results = {
        'qrof': [0.25, 0.25, 0.25, 0.25], 
        'bwm': [0.25, 0.25, 0.25, 0.25], 
        'swara': {k: 0.25 for k in CRITERIA_KEYS}
    }

    # 1. QROF-AHP Calculation
    try:
        if 'qrof' in data['mcdm']:
            matrix = [[float(c) for c in r] for r in data['mcdm']['qrof']['matrix']]
            qrof_engine = QROFAHP()
            w = qrof_engine.calculate_weights(matrix)
            results['qrof'] = [round(float(x), 4) for x in w]
    except Exception:
        print("ERROR: QROF Calculation Failed")
        traceback.print_exc()

    # 2. BWM Calculation
    try:
        if 'bwm' in data['mcdm']:
            bd = data['mcdm']['bwm']
            best_v = [float(x) for x in bd['best_vectors']]
            worst_v = [float(x) for x in bd['worst_vectors']]
            
            # Only run if expert has configured values (not all 1.0)
            if any(v > 1 for v in best_v):
                bwm_engine = BWM_VIKOR()
                k_map = {k: i for i, k in enumerate(CRITERIA_KEYS)}
                w = bwm_engine.solve_bwm_weights(
                    k_map[bd['best_criteria']], 
                    k_map[bd['worst_criteria']], 
                    best_v, 
                    worst_v
                )
                results['bwm'] = [round(float(x), 4) for x in w]
    except Exception:
        print("ERROR: BWM Calculation Failed")
        traceback.print_exc()

    # 3. SWARA Calculation
    try:
        if 'swara' in data['mcdm']:
            sd = data['mcdm']['swara']
            # Convert comparative scores to floats
            comps = [float(x) for x in sd.get('comparative_scores', [])]
            
            swara_engine = SWARA_MOORA()
            w_dict = swara_engine.calculate_swara_weights(sd['rank_order'], comps)
            # Ensure numbers are JSON-friendly
            results['swara'] = {k: round(float(v), 4) for k, v in w_dict.items()}
    except Exception:
        print("ERROR: SWARA Calculation Failed")
        traceback.print_exc()

    return jsonify(results)

# ==================== 3. RECOMMENDATION ENGINE ROUTE ====================

@app.route('/api/process_recommendation', methods=['POST'])
def process_recommendation():
    """Receives student input and returns ranked specializations using all 4 methods"""
    req_data = request.json
    student_scores = req_data['student_scores']
    expert_db = load_data()
    crit = expert_db.get('criteria', {})
    
    specs = ['ADE', 'AI', 'SDS', 'DE', 'NDC']
    spec_names = [
        'APPLICATION DEVELOPMENT ENGINEERING', 
        'ARTIFICIAL INTELLIGENCE', 
        'SECURITY IN DIGITAL SYSTEM', 
        'DATA ENGINEERING', 
        'NETWORK AND DATA COMMUNICATIONS'
    ]
    
    # Decision Matrix: 5 Alternatives (Rows) x 4 Criteria (Columns)
    mat = np.zeros((5, 4))
    
    def calc_weighted_score(scores, weights_map, is_skill=False):
        total_possible = 0
        weighted_score = 0
        for subject, importance in weights_map.items():
            raw_score = scores.get(subject, 0)
            # Normalize technical skills (1-10 to percentage)
            normalized = (raw_score - 1) * (100 / 9) if is_skill and raw_score > 0 else raw_score
            weighted_score += normalized * importance
            total_possible += 100 * importance
        return (weighted_score / total_possible) * 100 if total_possible > 0 else 0

    # Fill Matrix
    for i, s in enumerate(specs):
        # Column 0: SPM
        mat[i,0] = calc_weighted_score(student_scores['spm'], {k: int(v.get(s,5)) for k,v in crit.get('spm_results',{}).items()})
        # Column 1: Uni Results
        mat[i,1] = calc_weighted_score(student_scores['uni'], {k: int(v.get(s,5)) for k,v in crit.get('previous_semester',{}).items()})
        # Column 2: Technical Skills
        mat[i,2] = calc_weighted_score(student_scores['skills'], {k: int(v.get(s,5)) for k,v in crit.get('technical_skills',{}).items()}, True)
        # Column 3: RIASEC Aptitude
        r_w = expert_db['riasec_weights'].get(s, {})
        apt = sum(student_scores['riasec'].get(t,0)*r_w.get(t,0) for t in ['R','I','A','S','E','C'])
        max_apt = sum(abs(v)*2 for v in r_w.values()) or 1
        mat[i,3] = max(0, min(100, (apt+max_apt)/(2*max_apt)*100))

    final_results = {}
    
    def format_rankings(scores_dict):
        sorted_items = sorted(scores_dict.items(), key=lambda x: x[1], reverse=True)
        return [{'spec': k, 'score': round(v, 1), 'rank': i+1} for i, (k, v) in enumerate(sorted_items)]

    # 1. q-ROF-AHP Logic
    try:
        q_eng = QROFAHP(); w = q_eng.calculate_weights(expert_db['mcdm']['qrof']['matrix'])
        final_results['q-ROF-AHP'] = format_rankings(dict(zip(spec_names, q_eng.calculate_scores(mat, w))))
    except Exception: final_results['q-ROF-AHP'] = []
    
    # 2. BWM + VIKOR Logic
    try:
        b_eng = BWM_VIKOR(); bd = expert_db['mcdm']['bwm']; km = {k: i for i, k in enumerate(CRITERIA_KEYS)}
        w = b_eng.solve_bwm_weights(km[bd['best_criteria']], km[bd['worst_criteria']], bd['best_vectors'], bd['worst_vectors'])
        final_results['BWM+VIKOR'] = format_rankings(dict(zip(spec_names, b_eng.calculate_vikor(mat, w))))
    except Exception: final_results['BWM+VIKOR'] = []

    # 3. SWARA + MOORA Logic
    try:
        s_eng = SWARA_MOORA(); sd = expert_db['mcdm']['swara']
        wd = s_eng.calculate_swara_weights(sd['rank_order'], sd['comparative_scores'])
        w_arr = np.array([wd.get(k,0) for k in CRITERIA_KEYS])
        final_results['SWARA+MOORA-3NAG'] = format_rankings(dict(zip(spec_names, s_eng.calculate_moora(mat, w_arr))))
    except Exception: final_results['SWARA+MOORA-3NAG'] = []

    # 4. CRITIC + EDAS Logic
    try:
        ce_eng = CRITIC_EDAS(); sc, _ = ce_eng.execute(mat)
        final_results['LTSF-CRITIC-EDAS'] = format_rankings(dict(zip(spec_names, sc)))
    except Exception: final_results['LTSF-CRITIC-EDAS'] = []

    return jsonify(final_results)

if __name__ == '__main__':
    # Running on Port 5001 for API access
    app.run(port=5001, debug=True)