import os
import requests
import json
from flask import Flask, render_template, request, redirect, url_for, session

app = Flask(__name__)
app.secret_key = 'fyp_secret_key'

# Point this to your Backend API (Port 5001)
API_BASE_URL = os.getenv("API_URL", "http://127.0.0.1:5001")

# ==================== DATA CONSTANTS ====================

CRITERIA_LABELS = {
    "spm_results": "SPM Results", 
    "previous_semester": "Previous Semester", 
    "technical_skills": "Technical Skills", 
    "aptitude_test": "Aptitude Test"
}

CRITERIA_KEYS = ["spm_results", "previous_semester", "technical_skills", "aptitude_test"]

SPECIALIZATION_INFO = {
    "APPLICATION DEVELOPMENT ENGINEERING": {
        "subjects": ["Project Management in Software Engineering", "Requirements Engineering", "Software Design and Architecture", "Software Testing", "Software Quality Assurance", "Blockchain and Applications"],
        "careers": [{"title": "Software Developer", "desc": "Building applications and systems"}, {"title": "Full-Stack Developer", "desc": "Frontend and backend development"}]
    },
    "ARTIFICIAL INTELLIGENCE": {
        "subjects": ["Machine Learning", "Natural Language Processing", "Computer Vision", "Neural Networks", "Bio-inspired Computing", "Generative AI"],
        "careers": [{"title": "AI Engineer", "desc": "Designing intelligent systems"}, {"title": "Data Scientist", "desc": "Analyzing complex data sets"}]
    },
    "SECURITY IN DIGITAL SYSTEM": {
        "subjects": ["Privacy Engineering", "Malware Analysis", "Penetration Testing", "Cyber Physical Security", "Digital Forensics", "Applied Cryptography"],
        "careers": [{"title": "Cybersecurity Analyst", "desc": "Protecting systems from threats"}]
    },
    "DATA ENGINEERING": {
        "subjects": ["Statistics for Data Science", "Big Data Analytics", "Pattern Mining", "Brain Computational Analytics", "Data Visualization"],
        "careers": [{"title": "Data Engineer", "desc": "Building data pipelines"}]
    },
    "NETWORK AND DATA COMMUNICATIONS": {
        "subjects": ["Network Administration", "Advance Routing", "Cloud Infrastructure", "Network Security", "IoT Applications", "Wireless Networks"],
        "careers": [{"title": "Network Engineer", "desc": "Designing communication networks"}]
    }
}

RIASEC_QUESTIONS = [
    {"id": 1, "trait": "R", "text": "When building furniture, do you enjoy following technical diagrams?"},
    {"id": 2, "trait": "R", "text": "Do you prefer hands-on activities like fixing electronic devices?"},
    {"id": 3, "trait": "R", "text": "When playing video games, do you enjoy figuring out game mechanics?"},
    {"id": 4, "trait": "R", "text": "Have you enjoyed activities involving tools like repairing phones?"},
    {"id": 5, "trait": "R", "text": "Do you like organizing physical spaces for optimal workflow?"},
    {"id": 6, "trait": "I", "text": "When watching detective movies, do you try to solve the mystery?"},
    {"id": 7, "trait": "I", "text": "Do you research topics deeply online out of curiosity?"},
    {"id": 8, "trait": "I", "text": "Have you enjoyed solving complex puzzles like Sudoku?"},
    {"id": 9, "trait": "I", "text": "When learning, do you prefer understanding the 'why'?"},
    {"id": 10, "trait": "I", "text": "Do you enjoy analyzing patterns in everyday life?"},
    {"id": 11, "trait": "A", "text": "Have you designed creative social media posts?"},
    {"id": 12, "trait": "A", "text": "Do you enjoy innovative solutions to problems?"},
    {"id": 13, "trait": "A", "text": "When decorating, do you focus on unique aesthetics?"},
    {"id": 14, "trait": "A", "text": "Have you created original content like digital art?"},
    {"id": 15, "trait": "A", "text": "Do you enjoy brainstorming 'outside the box'?"},
    {"id": 16, "trait": "S", "text": "Do you help friends with technology problems?"},
    {"id": 17, "trait": "S", "text": "Have you enjoyed teaching concepts to classmates?"},
    {"id": 18, "trait": "S", "text": "Do you prefer working in team projects?"},
    {"id": 19, "trait": "S", "text": "Have you volunteered to organize events?"},
    {"id": 20, "trait": "S", "text": "Do people come to you for advice?"},
    {"id": 21, "trait": "E", "text": "Have you taken lead in organizing events?"},
    {"id": 22, "trait": "E", "text": "Do you enjoy convincing friends to try new tech?"},
    {"id": 23, "trait": "E", "text": "Have you managed a budget for a project?"},
    {"id": 24, "trait": "E", "text": "Do you naturally take charge?"},
    {"id": 25, "trait": "E", "text": "Have you successfully pitched an idea?"},
    {"id": 26, "trait": "C", "text": "Do you enjoy creating organized systems?"},
    {"id": 27, "trait": "C", "text": "Have you made detailed plans or checklists?"},
    {"id": 28, "trait": "C", "text": "Do you prefer following clear procedures?"},
    {"id": 29, "trait": "C", "text": "Have you enjoyed cataloging collections?"},
    {"id": 30, "trait": "C", "text": "Do you ensure all details are correct?"}
]

def convert_grade(grade):
    g = str(grade).upper().strip()
    return {'A+':95,'A':90,'A-':85,'B+':80,'B':75,'B-':70,'C+':65,'C':60,'D':45,'E':40}.get(g, 0)

# ==================== EXPERT ROUTES ====================

@app.route('/expert')
def expert_dashboard():
    try:
        data = requests.get(f"{API_BASE_URL}/api/get_data").json()
        weights = requests.get(f"{API_BASE_URL}/api/calculate_weights").json()
        return render_template('expert/dashboard.html', data=data, weights=weights)
    except:
        return "Error: Backend API (api.py) is not running on Port 5001."

@app.route('/expert/criteria', methods=['GET', 'POST'])
def expert_criteria():
    data = requests.get(f"{API_BASE_URL}/api/get_data").json()
    if request.method == 'POST':
        data['criteria'] = json.loads(request.form.get('criteria_json'))
        requests.post(f"{API_BASE_URL}/api/save_data", json=data)
        return redirect(url_for('expert_criteria'))
    return render_template('expert/criteria.html', data=data)

@app.route('/expert/riasec', methods=['GET', 'POST'])
def expert_riasec():
    data = requests.get(f"{API_BASE_URL}/api/get_data").json()
    if request.method == 'POST':
        data['riasec_weights'] = json.loads(request.form.get('riasec_json'))
        requests.post(f"{API_BASE_URL}/api/save_data", json=data)
        return redirect(url_for('expert_riasec'))
    return render_template('expert/riasec.html', data=data)

@app.route('/expert/qrof', methods=['GET', 'POST'])
def expert_qrof():
    data = requests.get(f"{API_BASE_URL}/api/get_data").json()
    if request.method == 'POST':
        matrix = []
        for i in range(4):
            row = []
            for j in range(4):
                val_str = request.form.get(f'cell_{i}_{j}')
                row.append(eval(val_str) if '/' in val_str else float(val_str))
            matrix.append(row)
        data['mcdm']['qrof']['matrix'] = matrix
        requests.post(f"{API_BASE_URL}/api/save_data", json=data)
        return redirect(url_for('expert_dashboard'))
    return render_template('expert/qrof.html', matrix=data['mcdm']['qrof']['matrix'], labels=list(CRITERIA_LABELS.values()))

@app.route('/expert/bwm_1', methods=['GET', 'POST'])
def expert_bwm_1():
    if request.method == 'POST':
        session['bwm_best'] = request.form.get('best')
        session['bwm_worst'] = request.form.get('worst')
        return redirect(url_for('expert_bwm_2'))
    return render_template('expert/bwm_step1.html', criteria=CRITERIA_LABELS)

@app.route('/expert/bwm_2', methods=['GET', 'POST'])
def expert_bwm_2():
    best, worst = session.get('bwm_best'), session.get('bwm_worst')
    if not best: return redirect(url_for('expert_bwm_1'))
    if request.method == 'POST':
        data = requests.get(f"{API_BASE_URL}/api/get_data").json()
        data['mcdm']['bwm'] = {
            "best_criteria": best, "worst_criteria": worst,
            "best_vectors": [float(request.form.get(f'best_to_{k}')) for k in CRITERIA_KEYS],
            "worst_vectors": [float(request.form.get(f'{k}_to_worst')) for k in CRITERIA_KEYS]
        }
        requests.post(f"{API_BASE_URL}/api/save_data", json=data)
        return redirect(url_for('expert_dashboard'))
    return render_template('expert/bwm_step2.html', best=best, worst=worst, keys=CRITERIA_KEYS, labels=CRITERIA_LABELS)

@app.route('/expert/swara_1', methods=['GET', 'POST'])
def expert_swara_1():
    if request.method == 'POST':
        ranks = sorted([(k, int(request.form.get(f'rank_{k}'))) for k in CRITERIA_KEYS], key=lambda x: x[1])
        session['swara_sorted_criteria'] = [x[0] for x in ranks]
        return redirect(url_for('expert_swara_2'))
    return render_template('expert/swara_step1.html', criteria=CRITERIA_LABELS)

@app.route('/expert/swara_2', methods=['GET', 'POST'])
def expert_swara_2():
    sorted_keys = session.get('swara_sorted_criteria')
    if not sorted_keys: return redirect(url_for('expert_swara_1'))
    if request.method == 'POST':
        data = requests.get(f"{API_BASE_URL}/api/get_data").json()
        data['mcdm']['swara'] = {
            "rank_order": sorted_keys,
            "comparative_scores": [float(request.form.get(f'sj_{sorted_keys[i]}', 0.1)) for i in range(1, 4)]
        }
        requests.post(f"{API_BASE_URL}/api/save_data", json=data)
        return redirect(url_for('expert_dashboard'))
    return render_template('expert/swara_step2.html', sorted_keys=sorted_keys, labels=CRITERIA_LABELS)

# ==================== STUDENT ROUTES ====================

@app.route('/')
def index(): 
    return render_template('index.html')

@app.route('/student/info', methods=['GET', 'POST'])
def student_info():
    if request.method == 'POST':
        session['student_info'] = request.form.to_dict()
        return redirect(url_for('student_spm'))
    return render_template('student/info.html')

@app.route('/student/spm', methods=['GET', 'POST'])
def student_spm():
    data = requests.get(f"{API_BASE_URL}/api/get_data").json()
    subjects = list(data['criteria'].get('spm_results', {}).keys())
    if request.method == 'POST':
        session['spm_scores'] = {s: convert_grade(request.form.get(s)) for s in subjects}
        return redirect(url_for('student_university'))
    return render_template('student/spm.html', subjects=subjects)

@app.route('/student/university', methods=['GET', 'POST'])
def student_university():
    data = requests.get(f"{API_BASE_URL}/api/get_data").json()
    subjects = list(data['criteria'].get('previous_semester', {}).keys())
    if request.method == 'POST':
        session['uni_scores'] = {s: convert_grade(request.form.get(s)) for s in subjects}
        return redirect(url_for('student_skills'))
    return render_template('student/university.html', subjects=subjects)

@app.route('/student/skills', methods=['GET', 'POST'])
def student_skills():
    data = requests.get(f"{API_BASE_URL}/api/get_data").json()
    skills = list(data['criteria'].get('technical_skills', {}).keys())
    if request.method == 'POST':
        session['skills_scores'] = {s: int(request.form.get(s) or 1) for s in skills}
        return redirect(url_for('student_riasec'))
    return render_template('student/skills.html', skills=skills)

@app.route('/student/riasec', methods=['GET', 'POST'])
def student_riasec():
    if request.method == 'POST':
        res = [int(request.form.get(f'q{i}') or 3) for i in range(1, 31)]
        mapped = [{1:-2, 2:-1, 3:0, 4:1, 5:2}[r] for r in res]
        traits = ['R','I','A','S','E','C']
        session['riasec_scores'] = {t: sum(mapped[i*5:(i+1)*5]) for i, t in enumerate(traits)}
        return redirect(url_for('student_results'))
    return render_template('student/riasec.html', questions=RIASEC_QUESTIONS)

@app.route('/student/results')
def student_results():
    if 'student_info' not in session: return redirect(url_for('index'))
    
    payload = {
        "student_scores": {
            "spm": session['spm_scores'], "uni": session['uni_scores'], 
            "skills": session['skills_scores'], "riasec": session['riasec_scores']
        }
    }
    # Call Backend API
    resp = requests.post(f"{API_BASE_URL}/api/process_recommendation", json=payload).json()
    
    method_results = resp['method_results']
    spec_names = ['APPLICATION DEVELOPMENT ENGINEERING', 'ARTIFICIAL INTELLIGENCE', 'SECURITY IN DIGITAL SYSTEM', 'DATA ENGINEERING', 'NETWORK AND DATA COMMUNICATIONS']
    
    # Simple Consensus (Average Ranks)
    tracker = {name: {'r':0, 's':0} for name in spec_names}
    for m in method_results:
        for item in method_results[m]:
            tracker[item['spec']]['r'] += item['rank']
            tracker[item['spec']]['s'] += item['score']
    
    consensus = [{'spec': k, 'avg_rank': v['r']/len(method_results), 'avg_score': v['s']/len(method_results)} for k,v in tracker.items()]
    consensus.sort(key=lambda x: x['avg_rank'])
    for i, c in enumerate(consensus, 1): c['rank'] = i
    
    top_spec_name = consensus[0]['spec']
    top_spec_info = SPECIALIZATION_INFO.get(top_spec_name, {"subjects":[], "careers":[]})
    weak_skills = [k for k,v in session['skills_scores'].items() if v < 6]

    return render_template('student/results.html', 
                           student=session['student_info'],
                           consensus=consensus, 
                           method_results=method_results,
                           agent_reasoning=resp['agent_reasoning'],
                           career_roadmap=resp['career_roadmap'],
                           top_spec_name=top_spec_name,
                           top_spec_info=top_spec_info,
                           weak_skills=weak_skills,
                           methods=method_results.keys())

if __name__ == '__main__':
    app.run(port=5000, debug=True)