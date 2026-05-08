import HealthKit

/// Biometric Risk Adjuster
/// Connects to Apple Watch to stream the operator's heart rate.
/// If heart rate exceeds 120 BPM during a drawdown, the system identifies panic 
/// and automatically cuts leverage by 50% to prevent irrational interference.
class SovereignHeartMonitor {
    let healthStore = HKHealthStore()

    func requestAuthorization() {
        let heartRateType = HKQuantityType.quantityType(forIdentifier: .heartRate)!
        healthStore.requestAuthorization(toShare: nil, read: [heartRateType]) { success, error in
            if success {
                print("[HEART] Connected to Biometric Vitals.")
            }
        }
    }

    func currentStressMultiplier(heartRate: Double) -> Double {
        if heartRate > 120.0 {
            print("[HEART] Operator panic detected. Reducing leverage.")
            return 0.5
        }
        return 1.0
    }
}
