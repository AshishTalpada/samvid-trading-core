import psutil

class PredictiveMaintenance:
    def check_system_health(self) -> bool:
        if psutil.cpu_percent() > 95.0 or psutil.virtual_memory().percent > 90.0:
            return False
        return True
