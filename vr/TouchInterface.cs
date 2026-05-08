using UnityEngine;

public class TouchInterface : MonoBehaviour {
    // "Touch" candles in VR to see "What-If" scenarios.
    void OnTriggerEnter(Collider other) {
        if(other.CompareTag("Candle")) {
            Debug.Log("Haptic Feedback: Recalculating portfolio delta based on touched candle.");
        }
    }
}
