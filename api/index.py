import os
import sys
import traceback
from flask import Flask, request, jsonify, render_template
from supabase import create_client

# =========================
# INIT - NO load_dotenv() on Vercel!
# =========================

# Vercel injects env vars directly into os.environ at runtime
# DO NOT use python-dotenv/load_dotenv() on Vercel - it doesn't work!

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')

# Fallback: Vercel sometimes renames 'templates' to 'template'
if not os.path.exists(TEMPLATE_DIR):
    ALT_TEMPLATE_DIR = os.path.join(BASE_DIR, 'template')
    if os.path.exists(ALT_TEMPLATE_DIR):
        TEMPLATE_DIR = ALT_TEMPLATE_DIR

print(f"[INIT] BASE_DIR: {BASE_DIR}", flush=True)
print(f"[INIT] TEMPLATE_DIR: {TEMPLATE_DIR}", flush=True)
print(f"[INIT] TEMPLATE_DIR exists: {os.path.exists(TEMPLATE_DIR)}", flush=True)

if os.path.exists(BASE_DIR):
    print(f"[INIT] Files in BASE_DIR: {os.listdir(BASE_DIR)}", flush=True)

app = Flask(__name__, template_folder=TEMPLATE_DIR)

# Read Supabase credentials from os.environ (Vercel injects these)
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

print(f"[INIT] SUPABASE_URL present: {bool(SUPABASE_URL)}", flush=True)
print(f"[INIT] SUPABASE_KEY present: {bool(SUPABASE_KEY)}", flush=True)

supabase = None
if SUPABASE_URL and SUPABASE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        print("[INIT] Supabase client created successfully", flush=True)
    except Exception as e:
        print(f"[INIT] Supabase init failed: {e}", flush=True)
else:
    print("[INIT] WARNING: Missing Supabase credentials", flush=True)


def sb(table):
    return supabase.table(table)


# =========================
# SAFE HELPERS
# =========================

def safe_select(table):
    if not supabase:
        return {"error": "Supabase not initialized - check env vars"}
    try:
        return sb(table).select("*").execute().data or []
    except Exception as e:
        print(f"[ERROR SELECT] {table}: {e}", flush=True)
        return {"error": str(e)}


def safe_insert(table, payload):
    if not supabase:
        return {"error": "Supabase not initialized - check env vars"}
    try:
        return sb(table).insert(payload).execute().data
    except Exception as e:
        print(f"[ERROR INSERT] {table}: {e}", flush=True)
        return {"error": str(e)}


# =========================
# ERROR HANDLER
# =========================

@app.errorhandler(Exception)
def handle_error(e):
    print(f"[UNHANDLED ERROR] {type(e).__name__}: {e}", flush=True)
    traceback.print_exc()
    return jsonify({"error": str(e), "type": type(e).__name__}), 500


# =========================
# FRONTEND
# =========================

@app.route("/")
def home():
    try:
        if os.path.exists(app.template_folder):
            files = os.listdir(app.template_folder)
            print(f"[HOME] Template files: {files}", flush=True)
        return render_template("index.html")
    except Exception as e:
        print(f"[ERROR RENDER] {type(e).__name__}: {e}", flush=True)
        traceback.print_exc()
        return jsonify({
            "error": f"Template error: {str(e)}",
            "type": type(e).__name__,
            "cwd": os.getcwd(),
            "base_dir": BASE_DIR,
            "template_folder": app.template_folder,
            "template_exists": os.path.exists(app.template_folder),
            "files_in_base": os.listdir(BASE_DIR) if os.path.exists(BASE_DIR) else []
        }), 500


# =========================
# STATS
# =========================

@app.route("/api/stats")
def stats():
    borrowers = safe_select("borrower")
    loans = safe_select("loan")
    payments = safe_select("payment")

    if isinstance(borrowers, dict) and "error" in borrowers:
        return jsonify(borrowers), 500

    active_portfolio = sum(
        float(l.get("principal_amount") or 0)
        for l in loans if isinstance(l, dict)
        if l.get("loan_status") == "Active"
    )

    total_collected = sum(
        float(p.get("amount_paid") or 0)
        for p in payments if isinstance(p, dict)
    )

    return jsonify({
        "borrowers": len(borrowers) if isinstance(borrowers, list) else 0,
        "loans": len(loans) if isinstance(loans, list) else 0,
        "active_portfolio": active_portfolio,
        "total_collected": total_collected
    })


# =========================
# BORROWERS
# =========================

@app.route("/api/borrowers", methods=["GET"])
def get_borrowers():
    return jsonify(safe_select("borrower"))


@app.route("/api/borrowers", methods=["POST"])
def add_borrower():
    data = request.json
    payload = {
        "full_name": data.get("full_name"),
        "email_address": data.get("email_address"),
        "phone_number": data.get("phone_number"),
        "home_address": data.get("home_address"),
        "date_of_birth": data.get("date_of_birth"),
        "income_level": data.get("income_level"),
        "credit_score": data.get("credit_score"),
    }
    return jsonify(safe_insert("borrower", payload))


@app.route("/api/borrowers/<int:bid>", methods=["DELETE"])
def delete_borrower(bid):
    try:
        return jsonify(sb("borrower").delete().eq("borrower_id", bid).execute().data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =========================
# STAFF
# =========================

@app.route("/api/staff", methods=["GET"])
def get_staff():
    return jsonify(safe_select("staff"))


@app.route("/api/staff", methods=["POST"])
def add_staff():
    data = request.json
    payload = {
        "staff_name": data.get("staff_name"),
        "role": data.get("role"),
        "department": data.get("department"),
    }
    return jsonify(safe_insert("staff", payload))


# =========================
# LOANS
# =========================

@app.route("/api/loans", methods=["GET"])
def get_loans():
    return jsonify(safe_select("loan"))


@app.route("/api/loans", methods=["POST"])
def add_loan():
    data = request.json
    payload = {
        "borrower_id": data.get("borrower_id"),
        "staff_id": data.get("staff_id"),
        "loan_type": data.get("loan_type"),
        "principal_amount": data.get("principal_amount"),
        "interest_rate": data.get("interest_rate"),
        "term_months": data.get("term_months"),
        "start_date": data.get("start_date"),
        "end_date": data.get("end_date"),
        "loan_status": data.get("loan_status", "Active"),
    }
    return jsonify(safe_insert("loan", payload))


# =========================
# PAYMENTS
# =========================

@app.route("/api/payments", methods=["GET"])
def get_payments():
    return jsonify(safe_select("payment"))


@app.route("/api/payments", methods=["POST"])
def add_payment():
    data = request.json
    payload = {
        "loan_id": data.get("loan_id"),
        "amount_paid": data.get("amount_paid"),
        "payment_date": data.get("payment_date"),
        "payment_method": data.get("payment_method"),
        "late_fee_applied": data.get("late_fee_applied", 0),
    }
    return jsonify(safe_insert("payment", payload))


# =========================
# COLLATERAL
# =========================

@app.route("/api/collateral", methods=["GET"])
def get_collateral():
    return jsonify(safe_select("collateral"))


@app.route("/api/collateral", methods=["POST"])
def add_collateral():
    data = request.json
    payload = {
        "loan_id": data.get("loan_id"),
        "asset_type": data.get("asset_type"),
        "market_value": data.get("market_value"),
        "asset_description": data.get("asset_description"),
    }
    return jsonify(safe_insert("collateral", payload))


# =========================
# DIAGNOSTICS
# =========================

@app.route("/api/health")
def health():
    template_files = []
    if os.path.exists(app.template_folder):
        template_files = os.listdir(app.template_folder)

    return jsonify({
        "status": "ok",
        "supabase_connected": bool(supabase),
        "supabase_url_set": bool(os.environ.get("SUPABASE_URL")),
        "supabase_key_set": bool(os.environ.get("SUPABASE_KEY")),
        "cwd": os.getcwd(),
        "base_dir": BASE_DIR,
        "template_folder": app.template_folder,
        "template_exists": os.path.exists(app.template_folder),
        "template_files": template_files,
        "base_files": os.listdir(BASE_DIR) if os.path.exists(BASE_DIR) else []
    })


@app.route("/api/debug/env")
def debug_env():
    """Debug endpoint - shows which env vars are available (names only, no values for security)"""
    env_names = sorted(os.environ.keys())
    supabase_related = [k for k in env_names if 'supabase' in k.lower()]

    return jsonify({
        "total_env_vars": len(env_names),
        "supabase_related_keys": supabase_related,
        "has_supabase_url": bool(os.environ.get("SUPABASE_URL")),
        "has_supabase_key": bool(os.environ.get("SUPABASE_KEY")),
        "all_keys": env_names  # You can remove this in production if you want
    })
