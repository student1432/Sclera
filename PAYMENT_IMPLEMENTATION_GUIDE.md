# Deep Dive: Implementing Razorpay for Institution Setup (India-Ready)

Since Stripe has restricted onboarding for new users in India, this guide provides the exact technical steps and code logic to implement **Razorpay**—the leading payment gateway for Indian businesses.

---

## 1. Environment & Config Setup
Add the following to your `.env` file:
```env
RAZORPAY_KEY_ID=rzp_test_...
RAZORPAY_KEY_SECRET=...
RAZORPAY_CURRENCY=INR
RAZORPAY_AMOUNT=299900 # Amount in paise (e.g., 2999.00 INR)
```

Update `config.py` to include these variables:
```python
class Config:
    # ... existing config ...
    RAZORPAY_KEY_ID = os.environ.get('RAZORPAY_KEY_ID')
    RAZORPAY_KEY_SECRET = os.environ.get('RAZORPAY_KEY_SECRET')
    RAZORPAY_AMOUNT = os.environ.get('RAZORPAY_AMOUNT', 299900)
```

## 2. Database Schema Shift
Modify the `signup_admin` function in `app.py`. We must ensure the institution is created in a "Locked" state.

**File: `app.py`**
```python
# Inside signup_admin POST handler
db.collection(INSTITUTIONS_COL).document(institution_id).set({
    'name': institution_name,
    'created_at': now,
    'created_by': uid,
    'status': 'pending_payment',
    'plan': 'Premium_Pending'
})
```

## 3. The Razorpay Integration Logic
Install the dependency: `pip install razorpay`.

### A. Create Razorpay Order
Unlike Stripe Checkout, Razorpay requires you to create an "Order" on the server first.

```python
import razorpay
client = razorpay.Client(auth=(app.config['RAZORPAY_KEY_ID'], app.config['RAZORPAY_KEY_SECRET']))

@app.route('/api/create-razorpay-order', methods=['POST'])
@require_admin_v2
def create_razorpay_order():
    uid = session.get('uid')
    admin_profile = _get_admin_profile(uid)

    data = {
        'amount': int(app.config['RAZORPAY_AMOUNT']),
        'currency': 'INR',
        'receipt': f"receipt_{admin_profile.get('institution_id')}",
        'notes': {
            'institution_id': admin_profile.get('institution_id'),
            'admin_uid': uid
        }
    }

    try:
        order = client.order.create(data=data)
        return jsonify(order)
    except Exception as e:
        return jsonify(error=str(e)), 400
```

### B. Verification & Activation
Implement the callback route to verify the payment signature.

```python
@app.route('/api/verify-payment', methods=['POST'])
@require_admin_v2
def verify_payment():
    data = request.json
    params_dict = {
        'razorpay_order_id': data.get('razorpay_order_id'),
        'razorpay_payment_id': data.get('razorpay_payment_id'),
        'razorpay_signature': data.get('razorpay_signature')
    }

    try:
        # Verify the signature
        client.utility.verify_payment_signature(params_dict)

        # Get institution_id from session or database
        uid = session.get('uid')
        admin_profile = _get_admin_profile(uid)
        institution_id = admin_profile.get('institution_id')

        # Activate the Institution
        db.collection(INSTITUTIONS_COL).document(institution_id).update({
            'status': 'active',
            'plan': 'Pro',
            'razorpay_payment_id': data.get('razorpay_payment_id'),
            'activated_at': datetime.utcnow().isoformat()
        })

        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'status': 'failure', 'error': str(e)}), 400
```

## 4. Middleware: The Gatekeeper
Update the `institution_admin_dashboard` to prevent access to unpaid accounts.

```python
@app.route('/institution/admin/dashboard')
@require_admin_v2
def institution_admin_dashboard():
    uid = session['uid']
    admin_profile = _get_admin_profile(uid) or {}
    institution_id = admin_profile.get('institution_id')

    # Check activation status
    inst_doc = db.collection(INSTITUTIONS_COL).document(institution_id).get()
    inst_data = inst_doc.to_dict() if inst_doc.exists else {}

    if inst_data.get('status') == 'pending_payment':
        return redirect(url_for('institution_checkout'))

    # ... rest of the existing dashboard logic ...
```

## 5. User Interface Requirements
*   **Checkout Page (`institution_checkout.html`):**
    *   Include the Razorpay script: `<script src="https://checkout.razorpay.com/v1/checkout.js"></script>`.
    *   A script to fetch the `order_id` and open the Razorpay modal.
    *   On success, call the `/api/verify-payment` endpoint.
*   **Success Page (`payment_success.html`):** Display a confirmation and redirect the user back to the dashboard.

---

## Technical Summary of Steps
1.  **Status Lock:** Ensure `status` is `pending_payment` on signup.
2.  **Order Creation:** Use Razorpay API to create an order on the server.
3.  **Frontend Modal:** Trigger the Razorpay Checkout modal with the `order_id`.
4.  **Signature Verification:** Use the `verify_payment_signature` utility to ensure authenticity.
5.  **Activation:** Update Firestore ONLY after successful signature verification.
