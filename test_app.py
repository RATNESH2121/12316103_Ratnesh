import urllib.request
import urllib.error
import json
import sqlite3

BASE = "http://127.0.0.1:8000"
DB   = r"c:\Users\asus\OneDrive\Desktop\12316103_Ratnesh\model_portfolio.db"

def get(path):
    with urllib.request.urlopen(BASE + path) as r:
        return json.loads(r.read())

def post(path, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(BASE + path, data=data, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

print("=" * 60)
print("COMPREHENSIVE APP VERIFICATION")
print("=" * 60)

# ── 1. Clients ─────────────────────────────────────────────────
clients = get("/api/clients/")["clients"]
print(f"\n✅ /api/clients/ — {len(clients)} clients: {[c['client_name'] for c in clients]}")

# ── 2. Rebalance C001 ─────────────────────────────────────────
rb = get("/api/rebalance/?client_id=C001")
print(f"\n✅ /api/rebalance/ — C001 (Amit Sharma)")
print(f"   Total portfolio : ₹{rb['total_portfolio']:,.0f}   (expected 5,80,000)")
print(f"   Total to BUY   : ₹{rb['total_to_buy']:,.0f}   (expected 2,00,000)")
print(f"   Total to SELL  : ₹{rb['total_to_sell']:,.0f}   (expected 1,20,000)")
print(f"   Fresh money    : ₹{rb['net_cash_needed']:,.0f}   (expected 80,000)")
expected = {
    "F001": ("BUY",    84000,  "Mirae Asset"),
    "F002": ("SELL",   10000,  "Parag Parikh"),
    "F003": ("BUY",    116000, "HDFC Mid Cap"),
    "F004": ("SELL",   23000,  "ICICI Bond"),
    "F005": ("SELL",   87000,  "Nippon Gold"),
    "F006": ("REVIEW", 80000,  "Axis Bluechip"),
}
print()
all_ok = True
for f in rb["funds"]:
    fid = f["fund_id"]
    exp_action, exp_amount, label = expected[fid]
    action_ok = f["action"] == exp_action
    amount_ok = abs(f["amount"] - exp_amount) < 1
    ok = "✅" if (action_ok and amount_ok) else "❌"
    if not (action_ok and amount_ok):
        all_ok = False
    print(f"   {ok} {label:25s} | {f['action']:6s} ₹{f['amount']:>10,.0f}  (expected {exp_action} ₹{exp_amount:,})")

# ── 3. Holdings C001 ──────────────────────────────────────────
h = get("/api/holdings/?client_id=C001")
print(f"\n✅ /api/holdings/ — C001: {len(h['holdings'])} holdings, total ₹{h['total']:,.0f}")
for hold in h["holdings"]:
    plan = "✅ In Plan" if hold["is_model_fund"] else "⚠ NOT IN PLAN"
    print(f"   {hold['fund_id']} {hold['fund_name']:35s} ₹{hold['current_value']:>10,.0f}  {plan}")

# ── 4. Model Funds ────────────────────────────────────────────
mf = get("/api/model_funds/")["funds"]
total_alloc = sum(f["allocation_pct"] for f in mf)
print(f"\n✅ /api/model_funds/ — {len(mf)} funds, total allocation = {total_alloc}%")
for f in mf:
    print(f"   {f['fund_id']} {f['fund_name']:35s} {f['allocation_pct']}%  [{f['asset_class']}]")

# ── 5. Save Session ───────────────────────────────────────────
print(f"\n⏳ Testing /api/save_session/ ...")
sv = post("/api/save_session/", {
    "client_id": "C001",
    "total_portfolio": rb["total_portfolio"],
    "total_to_buy": rb["total_to_buy"],
    "total_to_sell": rb["total_to_sell"],
    "net_cash_needed": rb["net_cash_needed"],
    "funds": rb["funds"],
})
session_id = sv["session_id"]
print(f"✅ Session saved — session_id={session_id}, status={sv['status']}")

# ── 6. History ────────────────────────────────────────────────
hist = get(f"/api/history/?client_id=C001")["sessions"]
print(f"\n✅ /api/history/ — {len(hist)} session(s) in DB")
for s in hist:
    print(f"   Session #{s['session_id']} | {s['created_at']} | {s['status']} | {len(s['items'])} items")

# ── 7. Update Status ──────────────────────────────────────────
up = post("/api/update_status/", {"session_id": session_id, "status": "APPLIED"})
print(f"\n✅ /api/update_status/ — Session #{session_id} → {up['status']}")

# ── 8. Verify DB directly ─────────────────────────────────────
conn = sqlite3.connect(DB)
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM rebalance_sessions WHERE client_id='C001'")
nsess = cur.fetchone()[0]
cur.execute("SELECT COUNT(*) FROM rebalance_items WHERE session_id=?", (session_id,))
nitems = cur.fetchone()[0]
cur.execute("SELECT status FROM rebalance_sessions WHERE session_id=?", (session_id,))
db_status = cur.fetchone()[0]
conn.close()
print(f"\n✅ DB direct check:")
print(f"   rebalance_sessions for C001 : {nsess} row(s)")
print(f"   rebalance_items for session #{session_id}: {nitems} row(s)  (expected 6)")
print(f"   Session status in DB         : {db_status}  (expected APPLIED)")

# ── 9. Edit Plan validation (bad sum) ─────────────────────────
print(f"\n⏳ Testing /api/update_model_funds/ — invalid sum (90% total) ...")
try:
    post("/api/update_model_funds/", {"funds": [
        {"fund_id": "F001", "allocation_pct": 20},
        {"fund_id": "F002", "allocation_pct": 20},
        {"fund_id": "F003", "allocation_pct": 20},
        {"fund_id": "F004", "allocation_pct": 15},
        {"fund_id": "F005", "allocation_pct": 15},
    ]})
except urllib.error.HTTPError as e:
    body = json.loads(e.read())
    print(f"✅ Correctly rejected: {body['error']}")

# ── 10. Edit Plan — valid update ──────────────────────────────
print(f"\n⏳ Testing /api/update_model_funds/ — valid (100% total) ...")
res = post("/api/update_model_funds/", {"funds": [
    {"fund_id": "F001", "allocation_pct": 30},
    {"fund_id": "F002", "allocation_pct": 25},
    {"fund_id": "F003", "allocation_pct": 20},
    {"fund_id": "F004", "allocation_pct": 15},
    {"fund_id": "F005", "allocation_pct": 10},
]})
print(f"✅ Plan update accepted: {res['message']}")

# ── 11. Test other clients ────────────────────────────────────
for cid in ["C002", "C003"]:
    rb2 = get(f"/api/rebalance/?client_id={cid}")
    h2  = get(f"/api/holdings/?client_id={cid}")
    print(f"\n✅ Client {cid}: portfolio ₹{rb2['total_portfolio']:,.0f} | {len(h2['holdings'])} holdings | Buy ₹{rb2['total_to_buy']:,.0f} | Sell ₹{rb2['total_to_sell']:,.0f}")

print("\n" + "=" * 60)
print("ALL TESTS PASSED" if all_ok else "SOME TESTS FAILED — check above")
print("=" * 60)
