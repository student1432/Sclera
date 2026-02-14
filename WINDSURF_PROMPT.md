# Master Implementation Prompt: Paid Institution Tiers (Razorpay)

Use this prompt in Windsurf for an automated, high-fidelity implementation of the Razorpay payment gateway, optimized for India.

---

**Task: Implement Razorpay Gateway for Institutional Onboarding**

**Objective:**
Convert the current free institution setup into a paid subscription flow. Gating the `institution_admin_dashboard` behind a Razorpay payment.

**Exact Implementation Steps:**

1.  **Dependency Addition:**
    *   Add `razorpay` to `requirements.txt`.

2.  **Configuration Overhaul:**
    *   In `config.py`, add `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, and `RAZORPAY_AMOUNT` to the `Config` class.
    *   Add placeholders for these in `.env`.

3.  **Routing & Logic (`app.py`):**
    *   **Signup Logic:** Update `@app.route('/signup/admin')`. Set institution `status` to `'pending_payment'`.
    *   **Checkout Route:** Create `@app.route('/institution/checkout')`. Renders `institution_checkout.html`. Pass `RAZORPAY_KEY_ID` and `RAZORPAY_AMOUNT` to the template.
    *   **Order API:** Create `@app.route('/api/create-razorpay-order', methods=['POST'])`.
        *   Use `client.order.create` with amount and currency ('INR').
    *   **Verification API:** Create `@app.route('/api/verify-payment', methods=['POST'])`.
        *   Use `client.utility.verify_payment_signature` to validate the payload.
        *   On success, update the Firestore `institutions` document: set `status` to `'active'` and `plan` to `'Pro'`.
    *   **Middleware Enforcement:** In `@app.route('/institution/admin/dashboard')`, redirect to `institution_checkout` if the institution status is `'pending_payment'`.

4.  **Template Creation:**
    *   **`templates/institution_checkout.html`**:
        *   Include `<script src="https://checkout.razorpay.com/v1/checkout.js"></script>`.
        *   Add a "Pay with Razorpay" button.
        *   Implement the JavaScript flow:
            1. Call `/api/create-razorpay-order`.
            2. Initialize Razorpay options with the `order_id`.
            3. On successful payment modal close, POST the results to `/api/verify-payment`.
            4. Redirect to dashboard on success.
    *   **`templates/payment_success.html`**:
        *   Show a professional success message with a 5-second redirect.

**Constraints:**
*   Maintain the "Dark Academic" aesthetic.
*   Use `INR` as the currency.
*   Strictly verify the signature on the server side.

**Database References:**
*   Collection: `institutions`
*   Status Field: `status` (values: `'pending_payment'`, `'active'`)

---
