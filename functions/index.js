const functions = require("firebase-functions");
const admin = require("firebase-admin");
admin.initializeApp();

const db = admin.firestore();

// -----------------------------------------------------------
// RESULT AGGREGATOR
// -----------------------------------------------------------
// Trigger: onCreate(results). Updates class summary.
exports.onResultCreated = functions.firestore
    .document("users/{userId}/exam_results/{resultId}")
    .onCreate(async (snap, context) => {
        const result = snap.data();
        const userId = context.params.userId;

        // Fetch user to get class info
        const userSnap = await db.collection("users").doc(userId).get();
        if (!userSnap.exists) return;
        const userData = userSnap.data();

        const classIds = userData.class_ids || [];
        if (!classIds.length) return;

        // For simplicity, we assume result applies to all classes (or use subject mappings)
        // Here we update all assigned classes
        const batch = db.batch();

        for (const classId of classIds) {
            const summaryRef = db.collection("classes").doc(classId).collection("class_summary").doc("latest");

            // Atomically increment total scores and counts
            batch.set(summaryRef, {
                total_assessments: admin.firestore.FieldValue.increment(1),
                total_score_sum: admin.firestore.FieldValue.increment(result.percentage || 0),
                last_updated: admin.firestore.FieldValue.serverTimestamp()
            }, { merge: true });
        }

        return batch.commit();
    });

// -----------------------------------------------------------
// AI DATA PREP (Minimal Logic)
// -----------------------------------------------------------
// Trigger: onWrite(study_mode)
exports.onStudySession = functions.firestore
    .document("users/{userId}/study_sessions/{sessionId}")
    .onWrite(async (change, context) => {
        // Just aggregates time for heatmap (simplified)
        const data = change.after.exists ? change.after.data() : null;
        if (!data) return;

        const dateKey = new Date().toISOString().split('T')[0]; // YYYY-MM-DD
        const hour = new Date().getHours();

        // This would go to a specialized aggregation collection
        // /institutions/{instId}/analytics/heatmap
    });
