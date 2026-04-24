import psutil

class SystemMonitor:
    @staticmethod
    def get_stats():
        return {
            "cpu_sys": psutil.cpu_percent(),
            "ram": psutil.virtual_memory().percent
        }
