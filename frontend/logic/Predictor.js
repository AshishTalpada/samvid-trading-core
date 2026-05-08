export function preRenderUI(mouseVelocity, eyeTracking) {
    // Dashboard pre-renders widgets before you ask based on eye tracking
    if (eyeTracking.target === "risk_panel") {
        console.log("Pre-fetching Risk Data to eliminate UI latency.");
    }
}
