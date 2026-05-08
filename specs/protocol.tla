---- MODULE protocol ----
VARIABLES state
Init == state = "RUNNING"
Next == state' = "RUNNING"
====
