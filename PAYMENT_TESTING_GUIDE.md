# Comprehensive Testing Guide: Institutional Payment (Razorpay)

Follow these exact steps to verify the robustness of your Razorpay integration.

---

## 🛠 Setup for Testing
1.  **Razorpay Keys:** Ensure you are using Test Mode keys (`rzp_test_...`).
2.  **Amount:** Set a small amount for testing (e.g., 100 paise for 1.00 INR).

---

## 🧪 Test Suite

### 1. The "Gatekeeper" Test
*   **Action:** Create a new Admin account at `/signup/admin`.
*   **Verification:**
    *   [ ] After registration, are you immediately on `/institution/checkout`?
    *   [ ] Try to manually type `/institution/admin/dashboard` in the URL bar. Do you get redirected back to checkout?
    *   [ ] In Firestore, does the institution have `status: "pending_payment"`?

### 2. The "Order Creation" Test
*   **Action:** Click the "Pay Now" button on the checkout page.
*   **Verification:**
    *   [ ] Does the Razorpay modal open successfully?
    *   [ ] Inspect the network tab for the POST to `/api/create-razorpay-order`. Does it return an order object with an ID?

### 3. The "Test Payment" Success Test
*   **Action:** In the Razorpay modal, select "Card" or "UPI" and use the test credentials provided by Razorpay (e.g., Success card).
*   **Verification:**
    *   [ ] After the modal closes, does the frontend call `/api/verify-payment`?
    *   [ ] Does the success page show a countdown or redirect you to the dashboard?
    *   [ ] **Database check:** Does the institution now have `status: "active"`, `plan: "Pro"`, and a `razorpay_payment_id`?

### 4. The "Signature Verification" Security Test
*   **Action:** Attempt to manually call `/api/verify-payment` with fake data.
*   **Verification:**
    *   [ ] Does the server return a `400 Bad Request` or a signature verification failure?
    *   [ ] Verify that the institution status remains `pending_payment`.

### 5. The "Payment Cancelled" Test
*   **Action:** Open the Razorpay modal, then close it without paying.
*   **Verification:**
    *   [ ] Does the page remain on `/institution/checkout`?
    *   [ ] Verify that the institution status is still `pending_payment`.

---

## 🚩 Common Failure Points to Watch For:
1.  **Paise vs. Rupees:** Razorpay amounts are in the smallest currency unit (paise). `100` = `1.00 INR`. Ensure your config reflects this.
2.  **Signature Mismatch:** Ensure you are using the correct `razorpay_order_id`, `razorpay_payment_id`, and `razorpay_signature` in the verification dictionary.
3.  **Frontend Success Callback:** Make sure the frontend only redirects to the success page AFTER the server-side verification returns a success status.
