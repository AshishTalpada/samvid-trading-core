import socket
import os
import subprocess

def check_ports(port_list):
    print(f"Scanning common IBKR ports: {port_list}")
    for port in port_list:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.5)
            result = s.connect_ex(('127.0.0.1', port))
            if result == 0:
                print(f"  [!] PORT {port} is OPEN and LISTENING.")
            else:
                pass

def list_running_processes():
    print("\nScanning for IBKR-related processes via tasklist...")
    try:
        output = subprocess.check_output("tasklist", shell=True).decode('utf-8', errors='ignore')
        lines = output.lower().splitlines()
        found = False
        for line in lines:
            if any(k in line for k in ["tws", "gateway", "ibhost", "interactive", "java"]):
                print(f"  [+] Found Process: {line[:50]}")
                found = True
        if not found:
            print("  [-] No IBKR-related processes found.")
    except Exception as e:
        print(f"Error checking processes: {e}")

if __name__ == "__main__":
    print("=== SETO V8.0 IBKR Diagnostic Scent ===")
    check_ports([7496, 7497, 4001, 4002, 7498, 4003])
    list_running_processes()
    print("\nPROMPT FOR USER:")
    print("If processes are active but all ports are 'closed', you MUST:")
    print("1. Go to TWS/Gateway -> Global Configuration -> API -> Settings")
    print("2. Check '[x] Enable ActiveX and Socket Clients'")
    print("3. Verify 'Socket port' matches 7497 or 4002.")
