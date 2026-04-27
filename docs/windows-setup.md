# Windows Setup

AmberClaw works great on Windows:

1. Ensure Python 3.11+ is installed.
2. Run `pip install amberclaw`.
3. To run as a background service on Windows, we recommend using NSSM (Non-Sucking Service Manager):

   ```cmd
   nssm install AmberClawGateway "C:\path\to\amberclaw.exe" gateway
   nssm start AmberClawGateway
   ```
