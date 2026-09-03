"""
Synthetic data generator.
Run: uv run python -m data.synthetic.generate --seed 42 --clients 60
Output: data/synthetic/clients.json  (60 synthetic clients with sessions,
         goals, consent records, actions, gold annotations)
Seed is fixed — output is deterministic.
"""
from __future__ import annotations

import argparse
import json
import random
import uuid
from datetime import datetime, timedelta
from pathlib import Path

SEED = 42

CATEGORIES = [
    "substance_use", "trauma_history", "forensic_legal",
    "sexual_health", "family_conflict", "medication", "financial", "safety_risk",
]

ROLES = ["counsellor", "social_worker", "psychiatrist", "nurse"]

SESSION_TEMPLATES = {
    "substance_use": [
        "Client disclosed ongoing alcohol use, approximately 4 units daily.",
        "Client reports being sober for 3 weeks following discharge.",
        "Client admitted to relapse over the weekend — returned to cannabis use.",
        "Discussed harm reduction strategies for substance use.",
    ],
    "trauma_history": [
        "Client referenced childhood abuse during session; did not elaborate.",
        "Trauma-informed approach used; client showed distress when discussing early life.",
        "Client expressed difficulty trusting care staff linked to past experiences.",
    ],
    "forensic_legal": [
        "Client has an upcoming court appearance on 14 March.",
        "Probation officer contacted regarding compliance.",
        "Client disclosed prior criminal conviction — not relevant to current episode.",
    ],
    "sexual_health": [
        "Client raised concerns about sexual health; referred to GUM clinic.",
        "STI screening discussed; client consented to referral.",
    ],
    "family_conflict": [
        "Family visit resulted in heightened distress; boundaries discussed.",
        "Client estranged from primary family; emergency contacts updated.",
        "Sibling requested information — consent not in place, declined.",
    ],
    "medication": [
        "Clozapine dose reviewed: 300mg nocte, no side effects reported.",
        "Client non-adherent with risperidone — discussed depot option.",
        "Lithium level checked: 0.7 mmol/L, within therapeutic range.",
    ],
    "financial": [
        "Client has outstanding rent arrears; social worker referral made.",
        "Benefits claim in progress; Universal Credit application submitted.",
    ],
    "safety_risk": [
        "Client expressed passive suicidal ideation; risk assessment completed.",
        "No current risk identified; protective factors strong.",
        "Client reported self-harm urges — safety plan reviewed and updated.",
    ],
    "general": [
        "Client engaged well in session; reported improved sleep.",
        "Discussed discharge goals and community support plan.",
        "Client attended OT group; participation noted as positive.",
        "Care coordinator handover planned for next week.",
        "Client set goal to attend weekly AA meeting.",
    ],
}

GOALS = [
    "Maintain sobriety for 30 days",
    "Attend all outpatient appointments",
    "Engage with community mental health team",
    "Rebuild contact with family",
    "Secure stable accommodation",
    "Complete medication compliance review",
    "Attend weekly therapy sessions",
    "Develop daily routine and sleep hygiene",
]

ACTION_TEMPLATES = [
    ("Schedule follow-up appointment with psychiatrist", "psychiatrist", "HIGH"),
    ("Submit benefits application", "social_worker", "MEDIUM"),
    ("Update safety plan with client", "counsellor", "HIGH"),
    ("Contact probation officer", "social_worker", "HIGH"),
    ("Arrange GP medication review", "nurse", "MEDIUM"),
    ("Refer to housing support", "social_worker", "HIGH"),
    ("Book GUM clinic appointment", "nurse", "MEDIUM"),
    ("Complete discharge summary", "counsellor", "HIGH"),
]


def gen_id() -> str:
    return str(uuid.uuid4())[:8]


def gen_client(rng: random.Random, client_num: int) -> dict:
    client_id = f"C{client_num:03d}"
    discharge_date = datetime(2025, 1, 1) + timedelta(days=rng.randint(0, 60))

    # Consent profile — each client has random consent settings
    consent_categories = rng.sample(CATEGORIES[:-1], k=rng.randint(2, 5))
    consents = []
    for cat in consent_categories:
        for role in rng.sample(ROLES, k=rng.randint(1, 3)):
            revoked = rng.random() < 0.12  # 12% chance of revoked
            revoked_at = None
            if revoked:
                revoked_at = (discharge_date + timedelta(days=rng.randint(1, 10))).isoformat()
            consents.append({
                "consent_id": gen_id(),
                "client_id": client_id,
                "category": cat,
                "recipient_role": role,
                "purpose": "handover",
                "granted": True,
                "granted_at": (discharge_date - timedelta(days=2)).isoformat(),
                "expires_at": (discharge_date + timedelta(days=90)).isoformat(),
                "revoked_at": revoked_at,
            })

    # Sessions — 4 to 7 sessions per client
    sessions = []
    n_sessions = rng.randint(4, 7)
    for i in range(n_sessions):
        session_cats = rng.sample(CATEGORIES, k=rng.randint(1, 3))
        session_cats.append("general")
        sentences = []
        spans = []
        for cat in session_cats:
            templates = SESSION_TEMPLATES.get(cat, SESSION_TEMPLATES["general"])
            text = rng.choice(templates)
            span_id = gen_id()
            sentences.append(text)
            if cat != "general":
                spans.append({
                    "span_id": span_id,
                    "text": text,
                    "category": cat,
                    "confidence": round(rng.uniform(0.55, 0.99), 2),
                    "is_safety_relevant": cat == "safety_risk",
                })
        sessions.append({
            "session_id": gen_id(),
            "client_id": client_id,
            "author_role": rng.choice(ROLES),
            "date": (discharge_date - timedelta(days=n_sessions - i)).isoformat(),
            "text": " ".join(sentences),
            "spans": spans,
        })

    # Goals
    n_goals = rng.randint(2, 4)
    goals = []
    for g in rng.sample(GOALS, k=n_goals):
        goals.append({
            "goal_id": gen_id(),
            "client_id": client_id,
            "text": g,
            "status": rng.choice(["active", "active", "completed", "on_hold"]),
            "priority": rng.choice(["HIGH", "MEDIUM", "LOW"]),
            "review_date": (discharge_date + timedelta(days=rng.randint(7, 30))).isoformat(),
        })

    # Pending actions
    n_actions = rng.randint(2, 5)
    actions = []
    for desc, owner_role, priority in rng.sample(ACTION_TEMPLATES, k=n_actions):
        actions.append({
            "action_id": gen_id(),
            "client_id": client_id,
            "description": desc,
            "owner_role": owner_role,
            "owner_id": f"STAFF_{gen_id()}",
            "due_date": (discharge_date + timedelta(days=rng.randint(3, 21))).isoformat(),
            "priority": priority,
            "status": rng.choice(["open", "open", "open", "in_progress"]),
            "escalation_level": 0,
        })

    # Gold annotations for evaluation
    consented_cats = {c["category"] for c in consents if not c["revoked_at"]}
    gold = {
        "permitted_categories": sorted(consented_cats),
        "withheld_categories": sorted(set(CATEGORIES) - consented_cats),
        "high_priority_actions": [a["action_id"] for a in actions if a["priority"] == "HIGH"],
        "has_safety_risk": any(
            s["category"] == "safety_risk"
            for sess in sessions for s in sess["spans"]
        ),
    }

    return {
        "client_id": client_id,
        "pseudonym": f"Patient-{client_num:03d}",
        "episode_id": gen_id(),
        "discharge_date": discharge_date.isoformat(),
        "consents": consents,
        "sessions": sessions,
        "goals": goals,
        "actions": actions,
        "gold": gold,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--clients", type=int, default=60)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    out_dir = Path(__file__).parent
    out_dir.mkdir(parents=True, exist_ok=True)

    clients = [gen_client(rng, i + 1) for i in range(args.clients)]

    with open(out_dir / "clients.json", "w") as f:
        json.dump({"seed": args.seed, "clients": clients}, f, indent=2)

    # Write seed file separately (protected by AGENTS.md)
    with open(out_dir / "seed.json", "w") as f:
        json.dump({"seed": args.seed, "clients": args.clients}, f, indent=2)

    print(f"✅ Generated {args.clients} synthetic clients → {out_dir / 'clients.json'}")


if __name__ == "__main__":
    main()
