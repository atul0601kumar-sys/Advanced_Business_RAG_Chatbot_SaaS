from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import boto3
from botocore.client import Config as BotoConfig

from app.core.config import Settings, get_settings


@dataclass
class StoredObject:
    uri: str
    key: str
    bucket: str | None


def get_storage_service(settings: Settings | None = None) -> "StorageService":
    return StorageService(settings or get_settings())


class StorageService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def store_bytes(self, *, object_group: str, workspace_id: str, object_id: str, filename: str, content: bytes) -> str:
        object_key = f"{object_group}/{workspace_id}/{object_id}/{sanitize_storage_name(filename)}"
        if self.settings.storage_backend == "local":
            root = Path(self.settings.storage_dir if object_group == "uploads" else self.settings.export_storage_dir).resolve()
            target_path = root / workspace_id / f"{object_id}_{sanitize_storage_name(filename)}"
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_bytes(content)
            try:
                target_path.chmod(int(self.settings.file_storage_permissions_mode, 8))
            except (ValueError, OSError):
                pass
            return str(target_path)
        if self.settings.storage_backend == "s3":
            self._s3_client().put_object(Bucket=self.settings.s3_bucket_name, Key=object_key, Body=content)
            return f"s3://{self.settings.s3_bucket_name}/{object_key}"
        if self.settings.storage_backend == "supabase":
            request = urllib.request.Request(
                f"{self.settings.supabase_url.rstrip('/')}/storage/v1/object/{self.settings.supabase_bucket_name}/{object_key}",
                data=content,
                headers={**self._supabase_headers(), "x-upsert": "true", "Content-Type": "application/octet-stream"},
                method="POST",
            )
            try:
                urllib.request.urlopen(request, timeout=20).read()
            except urllib.error.HTTPError as exc:
                raise RuntimeError(f"Supabase storage upload failed: {exc.read().decode('utf-8', errors='ignore')}") from exc
            return f"supabase://{self.settings.supabase_bucket_name}/{object_key}"
        raise RuntimeError(f"Unsupported storage backend: {self.settings.storage_backend}")

    def load_bytes(self, storage_uri: str) -> bytes:
        parsed = self._parse_uri(storage_uri)
        if parsed.uri.startswith("local://") or parsed.bucket is None and parsed.uri == parsed.key:
            return Path(parsed.key).read_bytes()
        if parsed.uri.startswith("s3://"):
            response = self._s3_client().get_object(Bucket=parsed.bucket, Key=parsed.key)
            return response["Body"].read()
        request = urllib.request.Request(
            f"{self.settings.supabase_url.rstrip('/')}/storage/v1/object/{parsed.bucket}/{parsed.key}",
            headers=self._supabase_headers(),
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.read()

    def delete(self, storage_uri: str | None) -> None:
        if not storage_uri:
            return
        parsed = self._parse_uri(storage_uri)
        if parsed.uri.startswith("local://") or parsed.bucket is None and parsed.uri == parsed.key:
            target = Path(parsed.key)
            if target.exists():
                target.unlink()
            return
        if parsed.uri.startswith("s3://"):
            self._s3_client().delete_object(Bucket=parsed.bucket, Key=parsed.key)
            return
        request = urllib.request.Request(
            f"{self.settings.supabase_url.rstrip('/')}/storage/v1/object/{parsed.bucket}/{parsed.key}",
            headers=self._supabase_headers(),
            method="DELETE",
        )
        urllib.request.urlopen(request, timeout=20).read()

    def exists(self, storage_uri: str | None) -> bool:
        if not storage_uri:
            return False
        parsed = self._parse_uri(storage_uri)
        if parsed.uri.startswith("local://") or parsed.bucket is None and parsed.uri == parsed.key:
            return Path(parsed.key).exists()
        try:
            if parsed.uri.startswith("s3://"):
                self._s3_client().head_object(Bucket=parsed.bucket, Key=parsed.key)
                return True
            request = urllib.request.Request(
                f"{self.settings.supabase_url.rstrip('/')}/storage/v1/object/info/{parsed.bucket}/{parsed.key}",
                headers=self._supabase_headers(),
            )
            with urllib.request.urlopen(request, timeout=20):
                return True
        except Exception:
            return False

    def generate_signed_url(self, storage_uri: str | None, *, download_name: str | None = None) -> str | None:
        if not storage_uri:
            return None
        parsed = self._parse_uri(storage_uri)
        if parsed.uri.startswith("s3://"):
            params: dict[str, Any] = {"Bucket": parsed.bucket, "Key": parsed.key}
            if download_name:
                params["ResponseContentDisposition"] = f'attachment; filename="{download_name}"'
            return self._s3_client().generate_presigned_url(
                "get_object",
                Params=params,
                ExpiresIn=self.settings.storage_signed_url_ttl_seconds,
            )
        if parsed.uri.startswith("supabase://"):
            request = urllib.request.Request(
                f"{self.settings.supabase_url.rstrip('/')}/storage/v1/object/sign/{parsed.bucket}/{parsed.key}",
                data=json.dumps({"expiresIn": self.settings.storage_signed_url_ttl_seconds}).encode("utf-8"),
                headers={**self._supabase_headers(), "Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
            signed_path = payload.get("signedURL")
            if not signed_path:
                return None
            return urllib.parse.urljoin(f"{self.settings.supabase_url.rstrip('/')}/storage/v1/", signed_path.lstrip("/"))
        return None

    def _parse_uri(self, storage_uri: str) -> StoredObject:
        if storage_uri.startswith("local://"):
            return StoredObject(uri=storage_uri, key=storage_uri.replace("local://", "", 1), bucket=None)
        if storage_uri.startswith("s3://") or storage_uri.startswith("supabase://"):
            _, remainder = storage_uri.split("://", 1)
            bucket, _, key = remainder.partition("/")
            return StoredObject(uri=storage_uri, key=key, bucket=bucket)
        return StoredObject(uri=storage_uri, key=storage_uri, bucket=None)

    def _s3_client(self):
        return boto3.client(
            "s3",
            endpoint_url=self.settings.s3_endpoint_url or None,
            region_name=self.settings.aws_region or None,
            aws_access_key_id=self.settings.s3_access_key_id or None,
            aws_secret_access_key=self.settings.s3_secret_access_key or None,
            config=BotoConfig(signature_version="s3v4"),
        )

    def _supabase_headers(self) -> dict[str, str]:
        if not self.settings.supabase_service_role_key:
            raise RuntimeError("SUPABASE_SERVICE_ROLE_KEY is required for Supabase Storage.")
        return {
            "apikey": self.settings.supabase_service_role_key,
            "Authorization": f"Bearer {self.settings.supabase_service_role_key}",
        }


def sanitize_storage_name(filename: str) -> str:
    return "".join(char if char.isalnum() or char in {".", "_", "-"} else "_" for char in filename).strip("._") or "document"
