import os
import sys
import traceback
import re
from datetime import datetime
from flask import Flask, request, jsonify, render_template
from supabase import create_client

# =========================
# INIT
# =========================

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_DIR = os.path.join(BASE_DIR, 'templates')

if not os.path.exists(TEMPLATE_DIR):
    ALT_TEMPLATE_DIR = os.path.join(BASE_DIR, 'template')
    if os.path.exists(ALT_TEMPLATE_DIR):
        TEMPLATE_DIR = ALT_TEMPLATE_DIR

print(f"[INIT] BASE_DIR: {BASE_DIR}", flush=True)
print(f"[INIT] TEMPLATE_DIR: {TEMPLATE_DIR}", flush=True)
print(f"[INIT] TEMPLATE_DIR exists: {os.path.exists(TEMPLATE_DIR)}", flush=True)

app = Flask(__name__, template_folder=TEMPLATE_DIR)

SUPABASE_URL = os.environ.get("SUPABASE_URL") or "https://qimsoxokcryekmlkhphi.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_KEY") or "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFpbXNveG9rY3J5ZWttbGtocGhpIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzgyNTUwMjgsImV4cCI6MjA5MzgzMTAyOH0.POOlpFOS5MGvVjyeIrLz5ja5gEKgd4vxHPTqdfUBf8A"

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
# VALIDATION HELPERS  <-- THIS IS WHAT WAS MISSING
# =========================

def validate_required(value, field_name):
    """Returns error string if value is empty/None, else None."""
    if not value or (isinstance(value, str) and not value.strip()):
        return f"{field_name} is required"
    return None


def validate_email(value):
    """Returns error string if email is invalid, else None."""
    if not value or not value.strip():
        return "Email address is required"
    pattern = r'^[^\s@]+@[^\s@]+\.[^\s@]+$'
    if not re.match(pattern, value.strip()):
        return "Email address is invalid"
    return None


def validate_phone(value):
    """Returns error string if phone is invalid, else None."""
    if not value or not value.strip():
        return "Phone number is required"
    digits = re.sub(r'\D', '', value)
    if len(digits) < 7 or len(digits) > 15:
        return "Phone number must be between 7 and 15 digits"
    return None


def validate_date(value, field_name):
    """Returns error string if date is missing or not YYYY-MM-DD, else None."""
    if not value or not str(value).strip():
        return f"{field_name} is required"
    try:
        datetime.strptime(str(value).strip(), '%Y-%m-%d')
    except ValueError:
        return f"{field_name} must be a valid date (YYYY-MM-DD)"
    return None


def validate_income(value):
    """Returns error string if income is invalid, else None."""
    if value is None or str(value).strip() == '':
        return "Income level is required"
    try:
        n = float(value)
        if n < 0:
            return "Income level cannot be negative"
    except (ValueError, TypeError):
        return "Income level must be a number"
    return None


def validate_credit_score(value):
    """Returns error string if credit score is out of range, else None."""
    if value is None or str(value).strip() == '':
        return "Credit score is required"
    try:
        n = int(value)
        if n < 300 or n > 850:
            return "Credit score must be between 300 and 850"
    except (ValueError, TypeError):
        return "Credit score must be a whole number"
    return None


def validate_positive_number(value, field_name, max_value=None):
    """Returns error string if value is not a positive number, else None."""
    if value is None or str(value).strip() == '':
        return f"{field_name} is required"
    try:
        n = float(value)
        if n <= 0:
            return f"{field_name} must be greater than zero"
        if max_value is not None and n > max_value:
            return f"{field_name} cannot exceed {max_value}"
    except (ValueError, TypeError):
        return f"{field_name} must be a valid number"
    return None


def validate_number(value, field_name, allow_negative=False):
    """Returns error string if value is not a number, else None."""
    if value is None or str(value).strip() == '':
        return f"{field_name} is required"
    try:
        float(value)
    except (ValueError, TypeError):
        return f"{field_name} must be a valid number"
    return None


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
        return render_template("index.html")
    except Exception as e:
        print(f"[ERROR RENDER] {type(e).__name__}: {e}", flush=True)
        traceback.print_exc()
        return jsonify({
            "error": f"Template error: {str(e)}",
            "template_folder": app.template_folder,
            "template_exists": os.path.exists(app.template_folder),
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
    data = request.json or {}

    errors = []
    errors.append(validate_required(data.get("full_name"), "Full name"))
    errors.append(validate_email(data.get("email_address")))
    errors.append(validate_phone(data.get("phone_number")))
    errors.append(validate_required(data.get("home_address"), "Home address"))
    errors.append(validate_date(data.get("date_of_birth"), "Date of birth"))
    errors.append(validate_income(data.get("income_level")))
    errors.append(validate_credit_score(data.get("credit_score")))

    errors = [e for e in errors if e]
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    payload = {
        "full_name": data["full_name"].strip(),
        "email_address": data["email_address"].strip().lower(),
        "phone_number": data["phone_number"].strip(),
        "home_address": data["home_address"].strip(),
        "date_of_birth": data["date_of_birth"],
        "income_level": float(data["income_level"]),
        "credit_score": int(data["credit_score"]),
    }
    result = safe_insert("borrower", payload)
    if isinstance(result, dict) and "error" in result:
        return jsonify(result), 500
    return jsonify(result)


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
    data = request.json or {}

    errors = []
    errors.append(validate_required(data.get("staff_name"), "Staff name"))
    errors.append(validate_required(data.get("role"), "Role"))
    errors.append(validate_required(data.get("department"), "Department"))

    errors = [e for e in errors if e]
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    payload = {
        "staff_name": data["staff_name"].strip(),
        "role": data["role"].strip(),
        "department": data["department"].strip(),
    }
    result = safe_insert("staff", payload)
    if isinstance(result, dict) and "error" in result:
        return jsonify(result), 500
    return jsonify(result)


@app.route("/api/staff/<int:sid>", methods=["DELETE"])
def delete_staff(sid):
    try:
        return jsonify(sb("staff").delete().eq("staff_id", sid).execute().data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =========================
# LOANS
# =========================

@app.route("/api/loans", methods=["GET"])
def get_loans():
    return jsonify(safe_select("loan"))


@app.route("/api/loans", methods=["POST"])
def add_loan():
    data = request.json or {}

    errors = []
    errors.append(validate_positive_number(data.get("borrower_id"), "Borrower ID"))
    errors.append(validate_positive_number(data.get("staff_id"), "Staff ID"))
    errors.append(validate_required(data.get("loan_type"), "Loan type"))
    errors.append(validate_positive_number(data.get("principal_amount"), "Principal amount"))
    errors.append(validate_positive_number(data.get("interest_rate"), "Interest rate", max_value=100))
    errors.append(validate_positive_number(data.get("term_months"), "Term (months)", max_value=600))
    errors.append(validate_date(data.get("start_date"), "Start date"))
    errors.append(validate_date(data.get("end_date"), "End date"))

    if data.get("start_date") and data.get("end_date"):
        try:
            start = datetime.strptime(data["start_date"], '%Y-%m-%d')
            end = datetime.strptime(data["end_date"], '%Y-%m-%d')
            if end <= start:
                errors.append("End date must be after start date")
        except ValueError:
            pass  # already caught by validate_date above

    errors = [e for e in errors if e]
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    payload = {
        "borrower_id": int(data["borrower_id"]),
        "staff_id": int(data["staff_id"]),
        "loan_type": data["loan_type"].strip(),
        "principal_amount": float(data["principal_amount"]),
        "interest_rate": float(data["interest_rate"]),
        "term_months": int(data["term_months"]),
        "start_date": data["start_date"],
        "end_date": data["end_date"],
        "loan_status": data.get("loan_status", "Active"),
    }
    result = safe_insert("loan", payload)
    if isinstance(result, dict) and "error" in result:
        return jsonify(result), 500
    return jsonify(result)


@app.route("/api/loans/<int:lid>", methods=["DELETE"])
def delete_loan(lid):
    try:
        # Delete associated payments and collateral first
        sb("payment").delete().eq("loan_id", lid).execute()
        sb("collateral").delete().eq("loan_id", lid).execute()
        return jsonify(sb("loan").delete().eq("loan_id", lid).execute().data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# =========================
# PAYMENTS
# =========================

@app.route("/api/payments", methods=["GET"])
def get_payments():
    return jsonify(safe_select("payment"))


@app.route("/api/payments", methods=["POST"])
def add_payment():
    data = request.json or {}

    errors = []
    errors.append(validate_positive_number(data.get("loan_id"), "Loan ID"))
    errors.append(validate_number(data.get("amount_paid"), "Amount paid", allow_negative=True))
    errors.append(validate_date(data.get("payment_date"), "Payment date"))
    errors.append(validate_required(data.get("payment_method"), "Payment method"))
    errors.append(validate_number(data.get("late_fee_applied"), "Late fee", allow_negative=True))

    errors = [e for e in errors if e]
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    payload = {
        "loan_id": int(data["loan_id"]),
        "amount_paid": float(data["amount_paid"]),
        "payment_date": data["payment_date"],
        "payment_method": data["payment_method"].strip(),
        "late_fee_applied": float(data.get("late_fee_applied") or 0),
    }
    result = safe_insert("payment", payload)
    if isinstance(result, dict) and "error" in result:
        return jsonify(result), 500
    return jsonify(result)


# =========================
# COLLATERAL
# =========================

@app.route("/api/collateral", methods=["GET"])
def get_collateral():
    return jsonify(safe_select("collateral"))


@app.route("/api/collateral", methods=["POST"])
def add_collateral():
    data = request.json or {}

    errors = []
    errors.append(validate_positive_number(data.get("loan_id"), "Loan ID"))
    errors.append(validate_required(data.get("asset_type"), "Asset type"))
    errors.append(validate_positive_number(data.get("market_value"), "Market value"))
    errors.append(validate_required(data.get("asset_description"), "Asset description"))

    errors = [e for e in errors if e]
    if errors:
        return jsonify({"error": "Validation failed", "details": errors}), 400

    payload = {
        "loan_id": int(data["loan_id"]),
        "asset_type": data["asset_type"].strip(),
        "market_value": float(data["market_value"]),
        "asset_description": data["asset_description"].strip(),
    }
    result = safe_insert("collateral", payload)
    if isinstance(result, dict) and "error" in result:
        return jsonify(result), 500
    return jsonify(result)


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
        "template_folder": app.template_folder,
        "template_exists": os.path.exists(app.template_folder),
        "template_files": template_files,
    })


@app.route("/api/debug/env")
def debug_env():
    env_names = sorted(os.environ.keys())
    supabase_related = [k for k in env_names if 'supabase' in k.lower()]
    return jsonify({
        "total_env_vars": len(env_names),
        "supabase_related_keys": supabase_related,
        "has_supabase_url": bool(os.environ.get("SUPABASE_URL")),
        "has_supabase_key": bool(os.environ.get("SUPABASE_KEY")),
    })
