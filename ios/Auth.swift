import Foundation
import LocalAuthentication

/// Biometric MFA Lock
/// Fingerprint + FaceID to unlock the core Sovereign Node command gateway.
class BiometricAuth {
    let context = LAContext()

    func authenticateUser(completion: @escaping (Bool) -> Void) {
        var error: NSError?
        if context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) {
            context.evaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, localizedReason: "Unlock Sovereign Apex Control") { success, authError in
                DispatchQueue.main.async {
                    if success {
                        print("[AUTH] Biometric ID Verified. Node Unlocked.")
                        completion(true)
                    } else {
                        print("[AUTH] Verification Failed.")
                        completion(false)
                    }
                }
            }
        } else {
            completion(false)
        }
    }
}
