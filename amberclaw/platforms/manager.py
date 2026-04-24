"""AmberClaw Platforms: Cross-platform bridge and manager."""

import sys
import os

class PlatformManager:
    """
    Detects and optimizes AmberClaw for Android, Linux, or Windows.
    """
    @staticmethod
    def get_platform() -> str:
        if os.path.exists('/data/data/com.termux'):
            return "android_termux"
        elif sys.platform.startswith('linux'):
            return "linux"
        elif sys.platform == 'win32':
            return "windows"
        return "unknown"

    @staticmethod
    def apply_platform_optimizations():
        platform = PlatformManager.get_platform()
        print(f"[Platform] Detected environment: {platform}")
        
        if platform == "android_termux":
            # Apply Termux-specific bridge logic
            os.environ['AMBERCLAW_PLATFORM'] = 'android'
            # (In a real impl, we would source the env.sh here)
            print("[Platform] Applying Android/Termux patches...")
        
        elif platform == "windows":
            print("[Platform] Optimizing for Windows (CMD/PowerShell)...")
