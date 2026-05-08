pub fn aegis_protocol_3() {
    // Aegis hardware-level auto-recovery
    // Triggers IPMI reboot if userland freezes
    std::process::Command::new("ipmitool").args(["chassis", "power", "reset"]).output().ok();
}
