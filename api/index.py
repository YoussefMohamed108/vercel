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
# First try env vars, then fall back to hardcoded values for testing
SUPABASE_URL = os.environ.get("SUPABASE_URL") or "https://qimsoxokcryekmlkhphi.supabase.co"
# NOTE: Using anon key here - if inserts fail due to RLS, switch to service_role key
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFpbXNveG9rY3J5ZWttbGtocGhpIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzgyNTUwMjgsImV4cCI6MjA5MzgzMTAyOH0.POOlpFOS5MGvVjyeIrLz5ja5gEKgd4vxHPTqdfUBf8A"

print(f"[INIT] SUPABASE_URL present: {bool(SUPABASE_URL)}", flush=True)
print(f"[INIT] SUPABASE_KEY present: {bool(SUPABASE_KEY)}", flush=True)
print(f"[INIT] SUPABASE_URL length: {len(SUPABASE_URL) if SUPABASE_URL else 0}", flush=True)
print(f"[INIT] SUPABASE_KEY length: {len(SUPABASE_KEY) if SUPABASE_KEY else 0}", flush=True)

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

    # Validate all fields
    errors = []
    errors.append(validate_required(data.get("full_name"), "Full name"))
    errors.append(validate_email(data.get("email_address")))
    errors.append(validate_phone(data.get("phone_number")))
    errors.append(validate_required(data.get("home_address"), "Home address"))
    errors.append(validate_date(data.get("date_of_birth"), "Date of birth"))
    errors.append(validate_income(data.get("income_level")))
    errors.append(validate_credit_score(data.get("credit_score")))

    # Remove None values (passed validations)
    errors = [e for e in errors if e]
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    payload = {
        "full_name": data.get("full_name").strip(),
        "email_address": data.get("email_address").strip().lower(),
        "phone_number": data.get("phone_number").strip(),
        "home_address": data.get("home_address").strip(),
        "date_of_birth": data.get("date_of_birth"),
        "income_level": float(data.get("income_level")),
        "credit_score": int(data.get("credit_score")),
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

    errors = []
    errors.append(validate_required(data.get("staff_name"), "Staff name"))
    errors.append(validate_required(data.get("role"), "Role"))
    errors.append(validate_required(data.get("department"), "Department"))

    errors = [e for e in errors if e]
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    payload = {
        "staff_name": data.get("staff_name").strip(),
        "role": data.get("role").strip(),
        "department": data.get("department").strip(),
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

    errors = []
    errors.append(validate_positive_number(data.get("borrower_id"), "Borrower ID"))
    errors.append(validate_positive_number(data.get("staff_id"), "Staff ID"))
    errors.append(validate_required(data.get("loan_type"), "Loan type"))
    errors.append(validate_positive_number(data.get("principal_amount"), "Principal amount"))
    errors.append(validate_positive_number(data.get("interest_rate"), "Interest rate", max_value=100))
    errors.append(validate_positive_number(data.get("term_months"), "Term (months)", max_value=600))
    errors.append(validate_date(data.get("start_date"), "Start date"))
    errors.append(validate_date(data.get("end_date"), "End date"))

    # Validate end date is after start date
    if data.get("start_date") and data.get("end_date"):
        from datetime import datetime
        start = datetime.strptime(data.get("start_date"), '%Y-%m-%d')
        end = datetime.strptime(data.get("end_date"), '%Y-%m-%d')
        if end <= start:
            errors.append("End date must be after start date")

    errors = [e for e in errors if e]
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    payload = {
        "borrower_id": int(data.get("borrower_id")),
        "staff_id": int(data.get("staff_id")),
        "loan_type": data.get("loan_type").strip(),
        "principal_amount": float(data.get("principal_amount")),
        "interest_rate": float(data.get("interest_rate")),
        "term_months": int(data.get("term_months")),
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

    errors = []
    errors.append(validate_positive_number(data.get("loan_id"), "Loan ID"))
    # Amount paid CAN be negative (refunds, chargebacks, corrections)
    errors.append(validate_number(data.get("amount_paid"), "Amount paid", allow_negative=True))
    errors.append(validate_date(data.get("payment_date"), "Payment date"))
    errors.append(validate_required(data.get("payment_method"), "Payment method"))
    # Late fee CAN be negative (fee reversals/credits)
    errors.append(validate_number(data.get("late_fee_applied"), "Late fee", allow_negative=True))

    errors = [e for e in errors if e]
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    payload = {
        "loan_id": int(data.get("loan_id")),
        "amount_paid": float(data.get("amount_paid")),
        "payment_date": data.get("payment_date"),
        "payment_method": data.get("payment_method").strip(),
        "late_fee_applied": float(data.get("late_fee_applied", 0) or 0),
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

    errors = []
    errors.append(validate_positive_number(data.get("loan_id"), "Loan ID"))
    errors.append(validate_required(data.get("asset_type"), "Asset type"))
    errors.append(validate_positive_number(data.get("market_value"), "Market value"))
    errors.append(validate_required(data.get("asset_description"), "Asset description"))

    errors = [e for e in errors if e]
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    payload = {
        "loan_id": int(data.get("loan_id")),
        "asset_type": data.get("asset_type").strip(),
        "market_value": float(data.get("market_value")),
        "asset_description": data.get("asset_description").strip(),
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
