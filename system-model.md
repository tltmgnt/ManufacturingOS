# System Model

## 1. State representation

Define the manufacturing state as:

\[
S_t = (D_t, B_t, R_t, P_t, M_t, F_t, Q_t, K_t, G_t)
\]

where:
- \(D_t\): design definition and revision;
- \(B_t\): bill of materials;
- \(R_t\): requirements and constraints;
- \(P_t\): process route;
- \(M_t\): material and tooling selections;
- \(F_t\): facility and capacity state;
- \(Q_t\): quality plan and quality evidence;
- \(K_t\): cost, yield, and schedule estimates;
- \(G_t\): risk and readiness state.

## 2. Agent function

For agent \(i\):

\[
A_i(S_t, C, E_i) \rightarrow (y_i, \mathcal{E}_i, U_i)
\]

- \(y_i\): proposed result;
- \(\mathcal{E}_i\): evidence and provenance;
- \(U_i\): uncertainty, assumptions, and open questions.

## 3. Feasibility

Let \(H_j(S)\) represent hard constraints and \(g_k(S)\) represent soft objectives.

The feasible set is:

\[
\mathcal{F} = \{S : H_j(S)=\text{true},\ \forall j\}
\]

Optimization occurs only over \(\mathcal{F}\):

\[
S^* = \arg\min_{S \in \mathcal{F}}
\left[
w_c C(S) + w_l L(S) + w_r R(S) + w_w W(S)
\right]
\]

where cost \(C\), lead time \(L\), risk \(R\), and waste \(W\) are defined by the selected use case. Weights must be documented and sensitivity-tested. If no feasible state exists, the system reports infeasibility rather than relaxing hard constraints silently.

## 4. Verification function

\[
V(Y,S_t,C) \in \{\text{PASS},\text{CONDITIONAL},\text{FAIL}\}
\]

- **PASS:** configured checks passed; human approvals may still be required.
- **CONDITIONAL:** no known hard-constraint violation, but specified evidence or approvals remain outstanding.
- **FAIL:** a hard constraint is violated, critical input is missing, or a material contradiction remains unresolved.

## 5. Important modeling limitations

A numerical score is not proof of manufacturability. Predictions depend on data quality, model validity, process variability, and operating conditions. Estimates must include assumptions and, where appropriate, ranges and sensitivity analysis.
