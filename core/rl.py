"""
Reinforcement-learning trading desk (Phase 11 — TensorTrade, Stable-Baselines3 custom env, RLlib, Intel Coach).

What these frameworks contribute and what is implemented here without torch:

  TensorTrade   → the *composition*: Exchange + Wallet/Portfolio + ActionScheme (BSH: buy/sell/hold) + RewardScheme
                  (SimpleProfit or *RiskAdjustedReturns* = differential Sharpe) + Observer(feature window) + Renderer.
                  → `TradingEnv` mirrors that API (reset/step/observation_space/action_space, gymnasium-compatible).
  SB3 (custom env) → agents: we implement tabular/linear **Q-learning with tile-coded state** and a **REINFORCE-style
                  linear policy gradient** (both classic, both used in Coach), plus an optional `sb3_backend()` that
                  trains real PPO/DQN if stable-baselines3 is installed.
  RLlib / Coach → evaluation discipline: many seeds, train/validation/test split by TIME, compare with buy&hold and a
                  random agent, report reward variance. RL on prices overfits spectacularly; the desk shows the OOS
                  collapse honestly (the research consensus — e.g. "Deep RL for trading" replication studies).
  Reward shaping lessons (TensorTrade docs): log-return reward with transaction-cost penalty and position-change penalty;
                  differential Sharpe (Moody & Saffell 1998) as risk-adjusted alternative.
"""
import numpy as np
import pandas as pd


# ------------------------------------------------------------------ environment (TensorTrade-like, gymnasium-compatible API)
class TradingEnv:
    """Discrete actions: 0=flat, 1=long, 2=short (BSH scheme + short). Observation: window of normalised features.
    Reward: log-return of the position minus costs (or differential Sharpe if reward='dsr')."""
    metadata = {"render_modes": []}

    def __init__(self, df, window=20, cost_bps=10.0, reward="logret", allow_short=True, feature_cols=None):
        self.df = df.reset_index(drop=True)
        self.window = window
        self.cost = cost_bps / 1e4
        self.reward_kind = reward
        self.allow_short = allow_short
        c = self.df["close"].values.astype(float)
        self.ret = np.diff(np.log(c), prepend=np.log(c[0]))
        feats = self._features(self.df) if feature_cols is None else self.df[feature_cols].values
        self.feats = feats
        self.n_actions = 3 if allow_short else 2
        self.obs_dim = feats.shape[1] * window + 1
        self.reset()

    @staticmethod
    def _features(df):
        c = df["close"]; h = df["high"]; l = df["low"]
        r = np.log(c).diff().fillna(0)
        f = pd.DataFrame({
            "r1": r, "r5": r.rolling(5).sum(), "r20": r.rolling(20).sum(),
            "vol20": r.rolling(20).std(), "rng": ((h - l) / c),
            "rsi": (lambda d: (100 - 100 / (1 + (d.clip(lower=0).rolling(14).mean() / (-d.clip(upper=0)).rolling(14).mean().replace(0, np.nan)))))(c.diff()) / 100 - 0.5,
            "ma_gap": (c / c.rolling(50).mean() - 1),
        }).fillna(0)
        # z-score each column on an expanding basis (no look-ahead)
        z = (f - f.expanding(50).mean()) / (f.expanding(50).std() + 1e-9)
        return z.fillna(0).clip(-5, 5).values

    def reset(self, seed=None, start=None, end=None):
        self.t = self.window if start is None else max(start, self.window)
        self.end = len(self.df) - 1 if end is None else min(end, len(self.df) - 1)
        self.pos = 0
        self.equity = [0.0]  # cumulative log-return
        self.A = self.B = 0.0  # differential-Sharpe moments
        self.trades = 0
        return self._obs(), {}

    def _obs(self):
        w = self.feats[self.t - self.window:self.t].ravel()
        return np.concatenate([w, [self.pos]]).astype(np.float32)

    def step(self, action):
        new_pos = {0: 0, 1: 1, 2: -1}[int(action)] if self.allow_short else {0: 0, 1: 1}[int(action)]
        cost = self.cost * abs(new_pos - self.pos)
        if new_pos != self.pos:
            self.trades += 1
        self.pos = new_pos
        self.t += 1
        r = self.pos * self.ret[self.t] - cost
        self.equity.append(self.equity[-1] + r)
        if self.reward_kind == "dsr":  # Moody & Saffell differential Sharpe ratio, eta=0.01
            eta = 0.01
            dA, dB = r - self.A, r * r - self.B
            denom = (self.B - self.A ** 2) ** 1.5
            reward = (self.B * dA - 0.5 * self.A * dB) / denom if denom > 1e-12 else r
            self.A += eta * dA; self.B += eta * dB
        else:
            reward = r
        done = self.t >= self.end
        return self._obs(), float(reward), done, False, {"logret": r, "pos": self.pos}

    # gymnasium-ish spaces (for SB3 backend)
    @property
    def observation_space(self):
        try:
            from gymnasium import spaces
            return spaces.Box(-np.inf, np.inf, (self.obs_dim,), np.float32)
        except Exception:
            return None

    @property
    def action_space(self):
        try:
            from gymnasium import spaces
            return spaces.Discrete(self.n_actions)
        except Exception:
            return None


# ------------------------------------------------------------------ agents
class LinearQAgent:
    """Q(s,a) = w_a · φ(s) with SGD TD(0) updates, ε-greedy; φ = obs (already normalised). Coach/SB3-DQN's linear cousin."""

    def __init__(self, obs_dim, n_actions, lr=1e-3, gamma=0.95, eps=0.2, eps_min=0.02, eps_decay=0.999, seed=0):
        self.rng = np.random.default_rng(seed)
        self.W = np.zeros((n_actions, obs_dim))
        self.b = np.zeros(n_actions)
        self.lr, self.gamma, self.eps, self.eps_min, self.eps_decay = lr, gamma, eps, eps_min, eps_decay

    def q(self, s):
        return self.W @ s + self.b

    def act(self, s, greedy=False):
        if not greedy and self.rng.random() < self.eps:
            return int(self.rng.integers(len(self.b)))
        return int(np.argmax(self.q(s)))

    def learn(self, s, a, r, s2, done):
        target = r + (0 if done else self.gamma * np.max(self.q(s2)))
        td = target - self.q(s)[a]
        self.W[a] += self.lr * td * s
        self.b[a] += self.lr * td
        self.eps = max(self.eps_min, self.eps * self.eps_decay)
        return td


class LinearPolicyAgent:
    """REINFORCE with a softmax-linear policy and a moving-average baseline (the policy-gradient baseline in Coach)."""

    def __init__(self, obs_dim, n_actions, lr=5e-4, seed=0):
        self.rng = np.random.default_rng(seed)
        self.W = np.zeros((n_actions, obs_dim)); self.b = np.zeros(n_actions)
        self.lr = lr; self.baseline = 0.0

    def probs(self, s):
        z = self.W @ s + self.b; z -= z.max(); p = np.exp(z); return p / p.sum()

    def act(self, s, greedy=False):
        p = self.probs(s)
        return int(np.argmax(p)) if greedy else int(self.rng.choice(len(p), p=p))

    def update_episode(self, S, A, R, gamma=0.99):
        G = np.zeros(len(R)); g = 0.0
        for i in range(len(R) - 1, -1, -1):
            g = R[i] + gamma * g; G[i] = g
        self.baseline = 0.9 * self.baseline + 0.1 * G.mean()
        adv = G - self.baseline
        for s, a, ad in zip(S, A, adv):
            p = self.probs(s)
            grad = -p[:, None] * s[None, :]; grad[a] += s
            self.W += self.lr * ad * grad
            gb = -p; gb[a] += 1; self.b += self.lr * ad * gb


def run_episode(env, agent, learn=True, start=None, end=None, kind="q"):
    s, _ = env.reset(start=start, end=end)
    S, A, R = [], [], []
    done = False
    while not done:
        a = agent.act(s, greedy=not learn)
        s2, r, done, _, info = env.step(a)
        if learn and kind == "q":
            agent.learn(s, a, r, s2, done)
        S.append(s); A.append(a); R.append(r)
        s = s2
    if learn and kind == "pg":
        agent.update_episode(S, A, R)
    eq = np.array(env.equity)
    return dict(total_logret=float(eq[-1]), max_dd=float((np.maximum.accumulate(eq) - eq).max()), trades=env.trades,
                sharpe=float(np.mean(np.diff(eq)) / (np.std(np.diff(eq)) + 1e-12) * np.sqrt(252)), equity=eq)


def train_and_evaluate(df, agent_kind="q", episodes=30, window=20, cost_bps=10.0, reward="logret", split=(0.6, 0.2, 0.2), seeds=(0, 1, 2), progress=None):
    """Time split train/val/test; several seeds; compare with buy&hold and random on the test set."""
    n = len(df)
    i_tr = int(n * split[0]); i_va = int(n * (split[0] + split[1]))
    env = TradingEnv(df, window=window, cost_bps=cost_bps, reward=reward)
    results = []
    curves = []
    for sd in seeds:
        if agent_kind == "pg":
            ag = LinearPolicyAgent(env.obs_dim, env.n_actions, seed=sd)
        else:
            ag = LinearQAgent(env.obs_dim, env.n_actions, seed=sd)
        hist = []
        best_val, best_W = -np.inf, None
        for ep in range(episodes):
            tr = run_episode(env, ag, learn=True, start=window, end=i_tr, kind=agent_kind)
            va = run_episode(env, ag, learn=False, start=i_tr, end=i_va, kind=agent_kind)
            hist.append((tr["total_logret"], va["total_logret"]))
            if va["total_logret"] > best_val:  # early stopping on validation (Coach/SB3 EvalCallback idea)
                best_val, best_W = va["total_logret"], (ag.W.copy(), ag.b.copy())
            if progress:
                progress(int((sd * episodes + ep + 1) / (len(seeds) * episodes) * 100), f"seed {sd} ep {ep + 1}")
        if best_W is not None:
            ag.W, ag.b = best_W
        te = run_episode(env, ag, learn=False, start=i_va, end=n - 1, kind=agent_kind)
        results.append(dict(seed=sd, train=hist[-1][0], val=best_val, test=te["total_logret"], test_dd=te["max_dd"], test_sharpe=te["sharpe"], trades=te["trades"]))
        curves.append(te["equity"])
    # baselines on test
    c = df["close"].values
    bh = float(np.log(c[-1] / c[i_va]))
    rng = np.random.default_rng(123)
    rand = []
    for _ in range(50):
        env.reset(start=i_va, end=n - 1); done = False; eq = 0.0
        while not done:
            _, r, done, _, _ = env.step(int(rng.integers(env.n_actions)))
        rand.append(env.equity[-1])
    res = pd.DataFrame(results)
    summary = dict(test_mean=float(res.test.mean()), test_std=float(res.test.std(ddof=0)), buy_hold=bh, random_mean=float(np.mean(rand)),
                   random_p95=float(np.percentile(rand, 95)), beats_bh=bool(res.test.mean() > bh), beats_random95=bool(res.test.mean() > np.percentile(rand, 95)),
                   train_mean=float(res.train.mean()), val_mean=float(res.val.mean()), overfit_gap=float(res.train.mean() - res.test.mean()))
    summary["bh_curve"] = np.log(c[i_va:n] / c[i_va]).tolist()
    return res, summary, curves


def sb3_backend(df, algo="PPO", timesteps=20000, window=20, cost_bps=10.0):
    """Train a real SB3 agent if stable-baselines3 + gymnasium are installed (optional heavy path)."""
    try:
        import gymnasium as gym
        from stable_baselines3 import PPO, DQN, A2C
    except Exception:
        return None
    class GymWrap(gym.Env):
        def __init__(self):
            self.e = TradingEnv(df, window, cost_bps)
            self.observation_space = self.e.observation_space; self.action_space = self.e.action_space
        def reset(self, seed=None, options=None):
            return self.e.reset(seed=seed)
        def step(self, a):
            return self.e.step(a)
    env = GymWrap()
    model = {"PPO": PPO, "DQN": DQN, "A2C": A2C}[algo]("MlpPolicy", env, verbose=0)
    model.learn(total_timesteps=timesteps)
    return model
