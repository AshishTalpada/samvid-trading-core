import Foundation
import LocalAuthentication
import CryptoKit

/// Zero-Trust Mobile Secure Bridge
/// End-to-end hardware-locked mobile control using Secure Enclave.
/// Generates and signs commands (like PANIC or LIQUIDATE) using FaceID/TouchID.
class SecureBridge {
    let context = LAContext()
    var privateKey: SecureEnclave.P256.Signing.PrivateKey?

    init() {
        do {
            self.privateKey = try SecureEnclave.P256.Signing.PrivateKey()
            print("[BRIDGE] Secure Enclave Keypair initialized.")
        } catch {
            print("[BRIDGE] FATAL: Secure Enclave not available.")
        }
    }

    /// Requires biometric authentication before signing an execution command
    func signCommandWithBiometrics(command: String, completion: @escaping (String?, Error?) -> Void) {
        var error: NSError?
        guard context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) else {
            completion(nil, error)
            return
        }

        context.evaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, localizedReason: "Authorize Sovereign Command: \(command)") { success, authError in
            if success {
                guard let key = self.privateKey else { return }
                let data = Data(command.utf8)
                do {
                    let signature = try key.signature(for: data)
                    let base64Sig = signature.derRepresentation.base64EncodedString()
                    print("[BRIDGE] Command signed securely. Sending to Sovereign Node.")
                    completion(base64Sig, nil)
                } catch {
                    completion(nil, error)
                }
            } else {
                print("[BRIDGE] Biometric verification failed.")
                completion(nil, authError)
            }
        }
    }
}
