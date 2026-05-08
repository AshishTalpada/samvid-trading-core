---- MODULE sovereign ----
VARIABLES system_state
Init == system_state = "SECURE"
Next == system_state' = "SECURE"
====
