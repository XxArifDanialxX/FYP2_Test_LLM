import numpy as np
from scipy.optimize import minimize

# ==================== METHOD 1: q-ROF-AHP ====================
class QROFAHP:
    def __init__(self, q=3):
        self.q = q

    def calculate_weights(self, pairwise_comparisons):
        matrix = np.array(pairwise_comparisons, dtype=float)
        n = len(matrix)
        q_scores = []

        for i in range(n):
            row_scores = []
            for j in range(n):
                val = matrix[i, j] if matrix[i, j] != 0 else 1
                mem = min(1, val / 9)
                non_mem = min(1, (1 / val) / 9)

                mem_q = mem ** self.q
                non_mem_q = non_mem ** self.q

                if mem_q + non_mem_q > 1:
                    scale = 1 / (mem_q + non_mem_q)
                    mem = (mem_q * scale) ** (1 / self.q)
                    non_mem = (non_mem_q * scale) ** (1 / self.q)
                row_scores.append((mem, non_mem))
            q_scores.append(row_scores)

        geo_means = []
        for i in range(n):
            prod_m, prod_nm = 1, 1
            for j in range(n):
                prod_m *= q_scores[i][j][0]
                prod_nm *= q_scores[i][j][1]
            geo_means.append((prod_m**(1/n), prod_nm**(1/n)))

        weights = []
        tot_m = sum(x[0] for x in geo_means)
        tot_nm = sum(x[1] for x in geo_means)
        denom = tot_m + n - tot_nm
        if denom == 0: denom = 1

        for m, nm in geo_means:
            w = (m + (1 - nm)) / denom
            weights.append(w)

        w_sum = sum(weights)
        return np.array(weights) / w_sum if w_sum != 0 else np.ones(n) / n

    def calculate_scores(self, matrix, weights):
        norm = np.zeros_like(matrix, dtype=float)
        for j in range(matrix.shape[1]):
            col = matrix[:, j]
            mn, mx = np.min(col), np.max(col)
            norm[:, j] = (col - mn) / (mx - mn) if mx - mn != 0 else 1
        return np.sum(norm * weights, axis=1) * 100

# ==================== METHOD 2: BWM + VIKOR ====================
class BWM_VIKOR:
    def solve_bwm_weights(self, best, worst, best_others, others_worst):
        def obj(w):
            max_dev = 0
            for i in range(len(w)):
                # Best-to-Others
                dev1 = abs(w[best] - best_others[i] * w[i])
                # Others-to-Worst
                dev2 = abs(w[i] - others_worst[i] * w[worst])
                max_dev = max(max_dev, dev1, dev2)
            return max_dev

        cons = ({'type': 'eq', 'fun': lambda w: np.sum(w) - 1})
        bounds = [(0.01, 1) for _ in range(4)]
        w0 = np.ones(4) / 4
        res = minimize(obj, w0, method='SLSQP', bounds=bounds, constraints=cons)
        return res.x

    def calculate_vikor(self, matrix, weights):
        ideal_best = np.max(matrix, axis=0)
        ideal_worst = np.min(matrix, axis=0)
        n, m = matrix.shape
        S = np.zeros(n)
        R = np.zeros(n)
        for i in range(n):
            dists = []
            for j in range(m):
                denom = ideal_best[j] - ideal_worst[j]
                d = weights[j] * (ideal_best[j] - matrix[i,j]) / (denom if denom != 0 else 1)
                dists.append(d)
            S[i] = sum(dists)
            R[i] = max(dists)
        
        S_min, S_max = min(S), max(S)
        R_min, R_max = min(R), max(R)
        Q = np.zeros(n)
        v = 0.5
        for i in range(n):
            t1 = (S[i]-S_min)/(S_max-S_min) if (S_max-S_min) != 0 else 0
            t2 = (R[i]-R_min)/(R_max-R_min) if (R_max-R_min) != 0 else 0
            Q[i] = v*t1 + (1-v)*t2
        return (1 - Q) * 100

# ==================== METHOD 3: SWARA + MOORA ====================
class SWARA_MOORA:
    def calculate_swara_weights(self, sorted_criteria, comparative_scores):
        n = len(sorted_criteria)
        q = [1.0] * n
        for i in range(1, n):
            s_j = comparative_scores[i-1] if i-1 < len(comparative_scores) else 0.1
            k_j = s_j + 1
            q[i] = q[i-1] / k_j
        
        total = sum(q)
        weights_list = [val/total for val in q]
        return dict(zip(sorted_criteria, weights_list))

    def calculate_moora(self, matrix, weights):
        # Ratio System
        norm = np.zeros_like(matrix)
        for j in range(matrix.shape[1]):
            denom = np.sqrt(np.sum(matrix[:, j]**2))
            norm[:, j] = matrix[:, j] / (denom if denom != 0 else 1)
        
        scores = np.sum(norm * weights, axis=1)
        mn, mx = np.min(scores), np.max(scores)
        return (scores - mn) / (mx - mn) * 100 if mx - mn != 0 else np.full(len(scores), 100)

# ==================== METHOD 4: LTSF-CRITIC-EDAS ====================
class CRITIC_EDAS:
    def execute(self, matrix):
        # Simplified CRITIC for weight calculation
        std = np.std(matrix, axis=0)
        corr = np.corrcoef(matrix, rowvar=False)
        if np.isnan(corr).any(): corr = np.eye(matrix.shape[1])
        info = std * np.sum(1 - corr, axis=1)
        weights = info / np.sum(info) if np.sum(info) != 0 else np.ones(matrix.shape[1])/matrix.shape[1]
        
        # EDAS
        avg = np.mean(matrix, axis=0)
        pda = np.maximum(0, (matrix - avg)) / (avg + 1e-9)
        nda = np.maximum(0, (avg - matrix)) / (avg + 1e-9)
        sp = np.sum(pda * weights, axis=1)
        sn = np.sum(nda * weights, axis=1)
        nsp = sp / (np.max(sp) + 1e-9)
        nsn = 1 - (sn / (np.max(sn) + 1e-9))
        return (nsp + nsn) / 2, weights