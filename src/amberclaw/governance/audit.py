"""
AmberClaw Governance: Audit System
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from loguru import logger


class AuditLogger:
    """Logs all agent actions for compliance and forensics."""
    
    def __init__(self, log_dir: str = "data/audit"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def log_action(self, agent_id: str, action: str, details: dict[str, Any]):
        """Log a specific action taken by an agent."""
        timestamp = datetime.utcnow().isoformat()
        log_entry = {
            "timestamp": timestamp,
            "agent_id": agent_id,
            "action": action,
            "details": details,
        }
        
        # Log to file
        log_file = self.log_dir / f"{datetime.utcnow().strftime('%Y-%m-%d')}.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
            
        logger.debug(f"Audit log entry created for {agent_id}: {action}")

# Global audit logger
auditor = AuditLogger()
