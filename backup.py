import os
import shutil
import hashlib
import base64
import boto3
from datetime import datetime
from typing import Optional

try:
    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
except ImportError:
    Fernet = None  


def _timestamped_dir(parent: str) -> str:
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    path = os.path.join(parent, f"backup_{ts}")
    os.makedirs(path, exist_ok=True)
    return path


def _get_most_recent_backup(parent: str) -> Optional[str]:
    if not os.path.isdir(parent):
        return None
    candidates = [
        os.path.join(parent, d)
        for d in os.listdir(parent)
        if os.path.isdir(os.path.join(parent, d)) and d.startswith("backup_")
    ]
    if not candidates:
        return None
    # Sorts by timestamp string naturally
    return sorted(candidates)[-1]


def _files_differ(src: str, dst: str) -> bool:
    if not os.path.exists(dst):
        return True
    return (
        os.path.getsize(src) != os.path.getsize(dst)
        or os.path.getmtime(src) != os.path.getmtime(dst)
    )


def backup_files(
    source_folder: str,
    backup_folder: str,
    incremental: bool = False,
) -> str:
    if not os.path.exists(source_folder):
        raise ValueError(f"Source folder does not exist: {source_folder}")

    os.makedirs(backup_folder, exist_ok=True)
    dest = _timestamped_dir(backup_folder)

    prev = None
    if incremental:
        prev = _get_most_recent_backup(backup_folder)

    for root, dirs, files in os.walk(source_folder):
        rel = os.path.relpath(root, source_folder)
        target_root = dest if rel == "." else os.path.join(dest, rel)
        
      
        os.makedirs(target_root, exist_ok=True)
        
        for fname in files:
            srcf = os.path.join(root, fname)
            dstf = os.path.join(target_root, fname)
            
            if incremental and prev:
                prevf = os.path.join(prev, rel, fname) if rel != "." else os.path.join(prev, fname)
                if not _files_differ(srcf, prevf):
                    continue
            
            shutil.copy2(srcf, dstf)
    return dest


def _derive_key(password: str, salt: bytes = b"aws-backup") -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100_000,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))


def encrypt_directory(directory: str, password: Optional[str]) -> str:
    if Fernet is None:
        raise RuntimeError("cryptography package not available. Install with: pip install cryptography")

  
    archive_path = shutil.make_archive(directory, "gztar", directory)
    

    key = _derive_key(password) if password else Fernet.generate_key()
    f = Fernet(key)
    
    with open(archive_path, "rb") as fin:
        data = fin.read()
    
    enc_path = archive_path + ".enc"
    with open(enc_path, "wb") as fout:
        fout.write(f.encrypt(data))
    

    os.remove(archive_path)
    return enc_path


def upload_to_s3(path: str, bucket: str, key_prefix: str = ""):
    s3 = boto3.client("s3")
    path_to_send = path
    
    if os.path.isdir(path):
        path_to_send = shutil.make_archive(path, "gztar", path)

    file_name = os.path.basename(path_to_send)
    s3_key = os.path.join(key_prefix, file_name).replace("\\", "/") # Ensure S3 slashes
    
    s3.upload_file(path_to_send, bucket, s3_key)
    return s3_key
def upload_to_glacier(path: str, vault_name: str) -> str:
    gl = boto3.client("glacier")
    path_to_send = path
    if os.path.isdir(path):
        path_to_send = shutil.make_archive(path, "gztar", path)
    with open(path_to_send, "rb") as f:
        resp = gl.upload_archive(vaultName=vault_name, body=f)
    return resp.get("archiveId", "Unknown ID")
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Flexible backup tool.")
    parser.add_argument("source", help="Folder to back up")
    parser.add_argument("backup", help="Backup parent directory")
    parser.add_argument("--incremental", action="store_true", help="Only copy changed files")
    parser.add_argument("--encrypt", action="store_true", help="Encrypt the backup")
    parser.add_argument("--password", help="Password for encryption")
    parser.add_argument("--s3-bucket", help="S3 bucket name")
    parser.add_argument("--s3-prefix", default="", help="S3 key prefix")
    parser.add_argument("--glacier-vault", help="AWS Glacier vault name")
    args = parser.parse_args()
    try:
        dst = backup_files(args.source, args.backup, incremental=args.incremental)
        print(f"[*] Local backup created: {dst}")
        if args.encrypt:
            dst = encrypt_directory(dst, args.password)
            print(f"[*] Encrypted: {dst}")d
        if args.s3_bucket:
            s3_path = upload_to_s3(dst, args.s3_bucket, args.s3_prefix)
            print(f"[*] Uploaded to S3: {args.s3_bucket}/{s3_path}")
        if args.glacier_vault:
            archive_id = upload_to_glacier(dst, args.glacier_vault)
            print(f"[*] Stored in Glacier. ID: {archive_id}")

    except Exception as exc:
        print(f"[!] Error: {exc}")
        import traceback
        traceback.print_exc()
