# Contextual Multi-Armed Bandits & Safe Policy Envelopes

PayRecover AI features a production-grade, mathematically rigorous **Contextual Multi-Armed Bandit (MAB)** subsystem built on **Disjoint Linear Upper Confidence Bound (LinUCB)** with **Safe Policy Envelopes**. This architecture allows the platform to learn optimal recovery action selection continuously while maintaining authoritative, non-negotiable financial guardrails.

---

## 1. Mathematical Formulation: Disjoint LinUCB

The bandit models the expected economic recovery reward for each candidate recovery arm $a \in \mathcal{A}$ conditioned on a 21-dimensional context vector $x \in \mathbb{R}^d$ ($d = 21$):

$$\mathbb{E}[R \mid x, a] = x^\top \theta_a^*$$

Each arm maintains its own disjoint ridge regression parameter vector $\hat{\theta}_a \in \mathbb{R}^d$, sufficient statistics matrix $A_a \in \mathbb{R}^{d \times d}$, and vector $b_a \in \mathbb{R}^d$:

$$A_a = \lambda I_d + \sum_{t \in \mathcal{T}_a} x_t x_t^\top$$
$$b_a = \sum_{t \in \mathcal{T}_a} R_t x_t$$
$$\hat{\theta}_a = A_a^{-1} b_a$$

Where:
* $\lambda > 0$ is the $L_2$ ridge regularization prior (default: $\lambda = 1.0$).
* $I_d$ is the $21 \times 21$ identity matrix.
* $\mathcal{T}_a$ is the set of all historical decision epochs where action $a$ was selected and an authoritative reward was observed.

### Decision Rule (Upper Confidence Bound)

At decision epoch $t$, with eligible action space $\mathcal{A}_{\text{eligible}}(x_t) \subseteq \mathcal{A}$:

$$a_t^* = \arg\max_{a \in \mathcal{A}_{\text{eligible}}(x_t)} \left( \hat{\theta}_a^\top x_t + \alpha \sqrt{x_t^\top A_a^{-1} x_t} \right)$$

* **Point Prediction (Exploitation)**: $\hat{R}_a(x_t) = \hat{\theta}_a^\top x_t$
* **Epistemic Exploration Bonus**: $\alpha \sqrt{x_t^\top A_a^{-1} x_t}$, where $\alpha \ge 0$ controls the exploration trade-off (default: $\alpha = 1.0$).
* **Deterministic Tie-Breaking**: Canonical alphabetical order by strategy identifier ensures strictly reproducible decisions across distributed workers.

### Online Incremental Updating

When an authoritative payment outcome is verified for action $a_t$ with context $x_t$ and economic reward $R_t$:

$$A_{a_t} \leftarrow A_{a_t} + x_t x_t^\top$$
$$b_{a_t} \leftarrow b_{a_t} + R_t x_t$$

---

## 2. Leak-Proof 21-Dimensional Feature Schema (v1.0)

Contextual features are strictly forward-looking, normalized, leak-proof, and contain zero Personally Identifiable Information (PII).

| Index | Feature Name | Range | Description |
|:-----:|:-------------|:-----:|:------------|
| 0 | `amount_log` | $[0.0, 1.0]$ | Log-scaled transaction value: $\min(1.0, \frac{\ln(1 + \text{amount})}{\ln(1000001)})$ |
| 1 | `amount_tier_micro` | $\{0.0, 1.0\}$ | 1 if $\text{amount} < ₹1,000$, 0 otherwise |
| 2 | `amount_tier_small` | $\{0.0, 1.0\}$ | 1 if $₹1,000 \le \text{amount} < ₹5,000$, 0 otherwise |
| 3 | `amount_tier_medium`| $\{0.0, 1.0\}$ | 1 if $₹5,000 \le \text{amount} < ₹20,000$, 0 otherwise |
| 4 | `amount_tier_large` | $\{0.0, 1.0\}$ | 1 if $₹20,000 \le \text{amount} < ₹50,000$, 0 otherwise |
| 5 | `amount_tier_jumbo` | $\{0.0, 1.0\}$ | 1 if $\text{amount} \ge ₹50,000$, 0 otherwise |
| 6 | `payment_method_card` | $\{0.0, 1.0\}$ | Credit / Debit card rail indicator |
| 7 | `payment_method_upi` | $\{0.0, 1.0\}$ | Unified Payments Interface (UPI) indicator |
| 8 | `payment_method_netbanking` | $\{0.0, 1.0\}$ | Netbanking gateway indicator |
| 9 | `payment_method_wallet` | $\{0.0, 1.0\}$ | Prepaid wallet indicator |
| 10 | `failure_category_insufficient_funds` | $\{0.0, 1.0\}$ | Balance/limit failure reason indicator |
| 11 | `failure_category_gateway_downtime` | $\{0.0, 1.0\}$ | Gateway/network timeout failure reason indicator |
| 12 | `failure_category_card_expired` | $\{0.0, 1.0\}$ | Instrument expiration failure reason indicator |
| 13 | `failure_category_auth_declined` | $\{0.0, 1.0\}$ | Issuer decline or authentication failure indicator |
| 14 | `retry_count_norm` | $[0.0, 1.0]$ | Prior retry attempts: $\min(1.0, \frac{\text{retry\_count}}{5.0})$ |
| 15 | `customer_intent_willing` | $\{0.0, 1.0\}$ | NLP intent classification: customer wants to complete payment |
| 16 | `customer_intent_disputing` | $\{0.0, 1.0\}$ | NLP intent classification: customer disputes charge/service |
| 17 | `customer_intent_hesitant` | $\{0.0, 1.0\}$ | NLP intent classification: price sensitivity or drop-off hesitation |
| 18 | `customer_prior_success_rate` | $[0.0, 1.0]$ | Merchant historical customer recovery rate (prior: 0.50 if n=0) |
| 19 | `is_quiet_hours` | $\{0.0, 1.0\}$ | 1 if local time is between 21:00 and 08:00 (TRAI compliance) |
| 20 | `bias` | $1.0$ | Stationary intercept term for ridge regression |

### Strict Temporal Barrier Guarantees

* **Temporal Barrier**: Customer historical success rate queries are constrained strictly to `created_at < decision_timestamp`. No future recovery outcomes or settlements are included in feature calculations.
* **Feature Schema Immutability**: All model features conform to schema version `"v1.0"`.

---

## 3. Safe Policy Envelopes: Authoritative Financial Guardrails

The contextual bandit is **never allowed to make unsafe decisions**. The decision engine enforces a hard two-tier architecture:

```
+-------------------------------------------------------------+
|             Incoming Context Vector x_t                     |
+-------------------------------------------------------------+
                                |
                                v
+-------------------------------------------------------------+
|       Tier 1: Authoritative Financial Guardrail Filter      |
|                                                             |
| * Amount >= ₹50,000           --> ESCALATE_TO_HUMAN ONLY   |
| * Retries >= Max Allowed      --> ESCALATE_TO_HUMAN ONLY   |
| * Insufficient Funds          --> Blocks Instant Retry     |
| * Quiet Hours (21:00 - 08:00) --> Blocks Urgent SMS/Call    |
| * Discount Cap (e.g., 10%)    --> Blocks High Discount Link|
+-------------------------------------------------------------+
                                |
                   Eligible Actions A_eligible(x_t)
                                |
                                v
+-------------------------------------------------------------+
|               Tier 2: LinUCB Policy Selector                |
|                                                             |
|           ArgMax_{a in A_eligible} [ Expected + Bonus ]     |
+-------------------------------------------------------------+
```

### Safety Envelope Invariants

1. **Jumbo Transaction Hard Escalation**: If `amount >= ₹50,000`, the action space is collapsed exclusively to `['ESCALATE_TO_HUMAN']`. Bandits cannot offer discounts or automated retries on jumbo liabilities.
2. **Exhausted Retries Invariant**: If `recovery_case.retry_count >= guardrail.max_retries`, all automated retries are pruned, forcing escalation.
3. **Liquidity Failure Invariant**: If `failure_reason == 'INSUFFICIENT_FUNDS'`, instant automated re-attempts are strictly blocked; actions must use spaced payment links or wait intervals.
4. **Discount Ceilings**: Discounted recovery actions exceeding `guardrail.max_discount_percentage` are immediately eliminated from candidate arms.

---

## 4. Bounded Economic Reward Function

To prevent large transaction amounts from skewing policy learning while rigorously optimizing merchant profitability, the objective reward function is strictly normalized:

$$R = \mathbf{1}_{\text{recovered}} \cdot (1.0 - \text{cost}_{\text{discount}}) - \mathbf{1}_{\text{not\_recovered}} \cdot 0.3 - \text{penalty}_{\text{retries}} - \text{penalty}_{\text{escalate}}$$

Where:
* **Base Recovery Term**: $+1.0$ upon verified settlement.
* **Discount Cost Ratio**: $-\frac{\text{discount\_amount}}{\text{payment\_amount}}$ (e.g., a 10% discount reduces recovery reward to $+0.90$).
* **Failure Penalty**: $-0.30$ if recovery fails or expires.
* **Excessive Retry Penalty**: $-0.05 \times \min(4, \text{retries})$.
* **Human Escalation Cost**: $-0.15$ if escalated to a human agent without successful recovery.
* **Authoritative Bounds**: $R \in [-0.5, 1.0]$.

---

## 5. Offline Policy Evaluation (OPE)

Before promoting any model revision, PayRecover AI evaluates candidate policies against historical logged outcomes using counterfactual causal inference.

### 1. Replay Estimator (Unbiased under Uniform Logging)

$$\hat{V}_{\text{Replay}}(\pi) = \frac{\sum_{i=1}^N \mathbf{1}(\pi(x_i) = a_i) \cdot R_i}{\sum_{i=1}^N \mathbf{1}(\pi(x_i) = a_i)}$$

### 2. Doubly Robust (DR) Estimator

The Doubly Robust estimator combines Inverse Propensity Scoring (IPS) with a Direct Method regression baseline $\hat{R}(x, a)$, providing lower variance while retaining asymptotic unbiasedness:

$$\hat{V}_{\text{DR}}(\pi) = \frac{1}{N} \sum_{i=1}^N \left( \hat{R}(x_i, \pi(x_i)) + \frac{\mathbf{1}(\pi(x_i) = a_i)}{p(a_i \mid x_i)} \left( R_i - \hat{R}(x_i, a_i) \right) \right)$$

* Propensity scores $p(a \mid x)$ are computed via uniform action space logging $p(a \mid x) = \frac{1}{|\mathcal{A}|}$ or empirical softmax frequency.
* Evaluation uses a **Temporal Train/Test Split** (first 70% of chronological records for model fitting, subsequent 30% for counterfactual testing) to guarantee zero look-ahead bias.

---

## 6. Shadow-Mode Execution & Safety Governance

In production, the bandit operates in **Shadow Mode**:
1. When the recovery pipeline is triggered, the authoritative Production Rule Engine makes the live customer decision.
2. Concurrently, the LinUCB model computes its recommended arm, predicted reward, epistemic confidence width, and guardrail envelope.
3. The shadow decision is durably logged to the `bandit_shadow_decisions` table with `is_agreement = (production_strategy == bandit_action)`.
4. When verified payment webhooks arrive, outcomes are reconciled to calculate the true economic reward $R$ without affecting live recovery traffic.

---

## 7. REST API Endpoints

| Method | Endpoint | Description |
|:-------|:---------|:------------|
| `GET` | `/api/bandits/status` | Current active policy configuration, exploration parameters, and learned ridge regression weights. |
| `GET` | `/api/bandits/shadow-decisions` | Paginated stream of shadow decisions with agreement tracking and filters. |
| `POST`| `/api/bandits/recommend` | Interactive decision preview with safe envelope inspection and feature attributions. |
| `POST`| `/api/bandits/evaluate` | Offline Policy Evaluation benchmark comparing LinUCB, Historical Best, $\epsilon$-Greedy, and Oracle. |
| `PUT` | `/api/bandits/parameters` | Dynamic hyperparameter tuning ($\alpha$ exploration rate, $\lambda$ ridge regularizer, safe envelopes). |
