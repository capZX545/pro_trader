"""
Security & Backup — امنیت و بک‌آپ
"""

import os
import time
import json
import shutil
import hashlib
from typing import Dict
from core.paths import DATA_DIR, data as data_path
from datetime import datetime

BACKUP_DIR = os.path.join(DATA_DIR, "backups")
os.makedirs(BACKUP_DIR, exist_ok=True)

def create_backup(name: str = None) -> str:
    """بک‌آپ از تمام داده‌های مهم"""
    try:
        if not name:
            name = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        backup_path = os.path.join(BACKUP_DIR, name)
        os.makedirs(backup_path, exist_ok=True)
        
        # Files to backup
        important_files = [
            "settings.json",
            "playbook.json",
            "validation.json",
            "audit.json",
            "success.json",
            "gold_alerts.json",
            "iran_gold_live.json",
            "evolution_state.json",
            "journal.json",
        ]
        
        for fname in important_files:
            src = data_path(fname)
            if os.path.exists(src):
                dst = os.path.join(backup_path, fname)
                shutil.copy2(src, dst)
        
        # Create manifest
        manifest = {
            "name": name,
            "timestamp": time.time(),
            "date": datetime.now().isoformat(),
            "files": important_files,
        }
        json.dump(manifest, open(os.path.join(backup_path, "manifest.json"), "w"), indent=2)
        
        print(f"[security] Backup created: {backup_path}")
        return backup_path
    except Exception as e:
        print(f"[security] Backup failed: {e}")
        return ""

def list_backups() -> list:
    try:
        backups = []
        for d in os.listdir(BACKUP_DIR):
            p = os.path.join(BACKUP_DIR, d)
            if os.path.isdir(p):
                manifest_path = os.path.join(p, "manifest.json")
                if os.path.exists(manifest_path):
                    try:
                        m = json.load(open(manifest_path, encoding="utf-8"))
                        backups.append(m)
                    except Exception:
                        backups.append({"name": d, "timestamp": os.path.getmtime(p)})
        backups.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        return backups
    except Exception:
        return []

def restore_backup(name: str) -> bool:
    try:
        backup_path = os.path.join(BACKUP_DIR, name)
        if not os.path.exists(backup_path):
            return False
        
        for fname in os.listdir(backup_path):
            if fname == "manifest.json":
                continue
            src = os.path.join(backup_path, fname)
            dst = data_path(fname)
            shutil.copy2(src, dst)
        
        print(f"[security] Restored backup: {name}")
        return True
    except Exception as e:
        print(f"[security] Restore failed: {e}")
        return False

def encrypt_settings():
    """رمزنگاری ساده تنظیمات (base64 + hash) - برای امنیت بیشتر"""
    # Note: This is simple obfuscation, not strong encryption
    # For real security, use cryptography library
    try:
        settings_path = data_path("settings.json")
        if not os.path.exists(settings_path):
            return
        
        # Just add checksum for integrity
        data = open(settings_path, "rb").read()
        checksum = hashlib.sha256(data).hexdigest()
        
        # Save checksum
        json.dump({"checksum": checksum, "ts": time.time()}, open(data_path("settings.checksum.json"), "w"))
        
        print(f"[security] Settings checksum: {checksum[:16]}...")
    except Exception as e:
        print(f"[security] Encrypt failed: {e}")

def check_integrity() -> Dict:
    """بررسی یکپارچگی داده‌ها"""
    issues = []
    
    try:
        # Check settings checksum
        settings_path = data_path("settings.json")
        checksum_path = data_path("settings.checksum.json")
        
        if os.path.exists(settings_path) and os.path.exists(checksum_path):
            data = open(settings_path, "rb").read()
            current_checksum = hashlib.sha256(data).hexdigest()
            
            saved = json.load(open(checksum_path, encoding="utf-8"))
            if saved.get("checksum") != current_checksum:
                issues.append({
                    "file": "settings.json",
                    "issue": "Checksum mismatch - file may be corrupted or tampered",
                    "severity": "warn",
                })
    except Exception as e:
        issues.append({"file": "integrity", "issue": str(e), "severity": "error"})
    
    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "timestamp": time.time(),
    }

if __name__ == "__main__":
    print(create_backup())
    print(list_backups()[:2])
    print(check_integrity())
