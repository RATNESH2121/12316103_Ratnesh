import sqlite3
import json
from datetime import datetime
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.shortcuts import render
from django.conf import settings


def get_db():
    """Return a sqlite3 connection to model_portfolio.db."""
    db_path = str(settings.DATABASES['default']['NAME'])
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def index(request):
    return render(request, 'core/index.html')


# ─── Screen 1: Rebalancing Calculation ────────────────────────────────────────

def api_rebalance(request):
    client_id = request.GET.get('client_id', 'C001')
    conn = get_db()
    cur = conn.cursor()

    # Get all holdings for client
    cur.execute(
        "SELECT fund_id, fund_name, current_value FROM client_holdings WHERE client_id = ?",
        (client_id,)
    )
    holdings = [dict(r) for r in cur.fetchall()]

    # Total portfolio value (ALL holdings including out-of-plan)
    total_portfolio = sum(h['current_value'] for h in holdings)

    # Get model funds (target allocations)
    cur.execute("SELECT fund_id, fund_name, asset_class, allocation_pct FROM model_funds")
    model_funds = {r['fund_id']: dict(r) for r in cur.fetchall()}

    # Known model fund IDs
    model_fund_ids = set(model_funds.keys())

    # Build holding lookup
    holding_lookup = {h['fund_id']: h for h in holdings}

    funds_result = []
    total_to_buy = 0
    total_to_sell = 0

    # Process model funds first
    for fund_id, mf in model_funds.items():
        target_pct = mf['allocation_pct']
        # Current value — may be 0 if fund in plan but not invested
        current_value = holding_lookup.get(fund_id, {}).get('current_value', 0)
        current_pct = (current_value / total_portfolio * 100) if total_portfolio > 0 else 0
        drift = target_pct - current_pct

        target_value = (target_pct / 100) * total_portfolio
        diff_amount = target_value - current_value  # positive=BUY, negative=SELL

        if diff_amount > 0.01:
            action = 'BUY'
            total_to_buy += diff_amount
        elif diff_amount < -0.01:
            action = 'SELL'
            total_to_sell += abs(diff_amount)
        else:
            action = 'HOLD'

        post_rebalance_pct = target_pct

        funds_result.append({
            'fund_id': fund_id,
            'fund_name': mf['fund_name'],
            'asset_class': mf['asset_class'],
            'is_model_fund': True,
            'current_value': round(current_value, 2),
            'current_pct': round(current_pct, 2),
            'target_pct': target_pct,
            'drift': round(drift, 2),
            'action': action,
            'amount': round(abs(diff_amount), 2),
            'post_rebalance_pct': round(post_rebalance_pct, 2),
        })

    # Process OUT-OF-PLAN funds (not in model_funds)
    for h in holdings:
        if h['fund_id'] not in model_fund_ids:
            current_pct = (h['current_value'] / total_portfolio * 100) if total_portfolio > 0 else 0
            funds_result.append({
                'fund_id': h['fund_id'],
                'fund_name': h['fund_name'],
                'asset_class': None,
                'is_model_fund': False,
                'current_value': round(h['current_value'], 2),
                'current_pct': round(current_pct, 2),
                'target_pct': None,
                'drift': None,
                'action': 'REVIEW',
                'amount': round(h['current_value'], 2),
                'post_rebalance_pct': None,
            })

    net_cash_needed = total_to_buy - total_to_sell
    conn.close()

    return JsonResponse({
        'client_id': client_id,
        'total_portfolio': round(total_portfolio, 2),
        'total_to_buy': round(total_to_buy, 2),
        'total_to_sell': round(total_to_sell, 2),
        'net_cash_needed': round(net_cash_needed, 2),
        'funds': funds_result,
    })


# ─── Screen 1: Save Recommendation ───────────────────────────────────────────

@csrf_exempt
def api_save_session(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    data = json.loads(request.body)
    client_id = data.get('client_id')
    portfolio_value = data.get('total_portfolio')
    total_to_buy = data.get('total_to_buy')
    total_to_sell = data.get('total_to_sell')
    net_cash_needed = data.get('net_cash_needed')
    funds = data.get('funds', [])
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    conn = get_db()
    cur = conn.cursor()

    # Insert rebalance_session
    cur.execute(
        """INSERT INTO rebalance_sessions
           (client_id, created_at, portfolio_value, total_to_buy, total_to_sell, net_cash_needed, status)
           VALUES (?, ?, ?, ?, ?, ?, 'PENDING')""",
        (client_id, created_at, portfolio_value, total_to_buy, total_to_sell, net_cash_needed)
    )
    session_id = cur.lastrowid

    # Insert rebalance_items
    for f in funds:
        cur.execute(
            """INSERT INTO rebalance_items
               (session_id, fund_id, fund_name, action, amount,
                current_pct, target_pct, post_rebalance_pct, is_model_fund)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                f.get('fund_id'),
                f.get('fund_name'),
                f.get('action'),
                f.get('amount'),
                f.get('current_pct'),
                f.get('target_pct'),
                f.get('post_rebalance_pct'),
                1 if f.get('is_model_fund') else 0,
            )
        )

    conn.commit()
    conn.close()

    return JsonResponse({'session_id': session_id, 'status': 'PENDING'})


# ─── Screen 3: History ────────────────────────────────────────────────────────

def api_history(request):
    client_id = request.GET.get('client_id', 'C001')
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """SELECT session_id, client_id, created_at, portfolio_value,
                  total_to_buy, total_to_sell, net_cash_needed, status
           FROM rebalance_sessions
           WHERE client_id = ?
           ORDER BY created_at DESC""",
        (client_id,)
    )
    sessions = [dict(r) for r in cur.fetchall()]

    # For each session, get items
    for s in sessions:
        cur.execute(
            """SELECT fund_id, fund_name, action, amount, current_pct, target_pct, is_model_fund
               FROM rebalance_items WHERE session_id = ?""",
            (s['session_id'],)
        )
        s['items'] = [dict(r) for r in cur.fetchall()]

    conn.close()
    return JsonResponse({'sessions': sessions})


@csrf_exempt
def api_update_status(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    data = json.loads(request.body)
    session_id = data.get('session_id')
    status = data.get('status')  # APPLIED or DISMISSED

    if status not in ('APPLIED', 'DISMISSED', 'PENDING'):
        return JsonResponse({'error': 'Invalid status'}, status=400)

    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "UPDATE rebalance_sessions SET status = ? WHERE session_id = ?",
        (status, session_id)
    )
    conn.commit()
    conn.close()
    return JsonResponse({'session_id': session_id, 'status': status})


# ─── Screen 2: Current Holdings ──────────────────────────────────────────────

def api_holdings(request):
    client_id = request.GET.get('client_id', 'C001')
    conn = get_db()
    cur = conn.cursor()

    cur.execute(
        """SELECT ch.fund_id, ch.fund_name, ch.current_value,
                  CASE WHEN mf.fund_id IS NOT NULL THEN 1 ELSE 0 END as is_model_fund
           FROM client_holdings ch
           LEFT JOIN model_funds mf ON ch.fund_id = mf.fund_id
           WHERE ch.client_id = ?
           ORDER BY ch.current_value DESC""",
        (client_id,)
    )
    holdings = [dict(r) for r in cur.fetchall()]
    total = sum(h['current_value'] for h in holdings)
    conn.close()

    return JsonResponse({'holdings': holdings, 'total': round(total, 2)})


# ─── Screen 4: Model Funds (Edit Plan) ───────────────────────────────────────

def api_model_funds(request):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT fund_id, fund_name, asset_class, allocation_pct FROM model_funds ORDER BY fund_id")
    funds = [dict(r) for r in cur.fetchall()]
    conn.close()
    return JsonResponse({'funds': funds})


@csrf_exempt
def api_update_model_funds(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    data = json.loads(request.body)
    updates = data.get('funds', [])  # [{fund_id, allocation_pct}, ...]

    total = sum(float(u['allocation_pct']) for u in updates)
    if abs(total - 100.0) > 0.01:
        return JsonResponse({'error': f'Allocations must sum to 100%. Current sum: {total:.2f}%'}, status=400)

    conn = get_db()
    cur = conn.cursor()
    for u in updates:
        cur.execute(
            "UPDATE model_funds SET allocation_pct = ? WHERE fund_id = ?",
            (float(u['allocation_pct']), u['fund_id'])
        )
    conn.commit()
    conn.close()

    return JsonResponse({'success': True, 'message': 'Plan updated successfully.'})


# ─── Clients list ─────────────────────────────────────────────────────────────

def api_clients(request):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT client_id, client_name, total_invested FROM clients ORDER BY client_id")
    clients = [dict(r) for r in cur.fetchall()]
    conn.close()
    return JsonResponse({'clients': clients})
