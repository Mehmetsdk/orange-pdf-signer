"""
storage.py — Cloudflare R2 (S3-compatible) storage helpers.

Uploads signature images and signed PDFs to the R2 bucket.
Credentials are read from environment variables:
    R2_ACCESS_KEY_ID
    R2_SECRET_ACCESS_KEY
    R2_ENDPOINT_URL
    R2_BUCKET_NAME
"""

import os
import io
import boto3
from botocore.exceptions import ClientError, NoCredentialsError


def _get_client():
    """Create and return a boto3 S3 client configured for Cloudflare R2."""
    access_key  = os.environ.get("R2_ACCESS_KEY_ID")
    secret_key  = os.environ.get("R2_SECRET_ACCESS_KEY")
    endpoint    = os.environ.get("R2_ENDPOINT_URL")

    if not all([access_key, secret_key, endpoint]):
        raise RuntimeError(
            "R2 credentials not set. "
            "Please configure R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, and R2_ENDPOINT_URL."
        )

    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name="auto",
    )


def _bucket() -> str:
    name = os.environ.get("R2_BUCKET_NAME", "orange-pdf-signer")
    return name


def upload_signature(username: str, file_bytes: bytes, filename: str) -> tuple[bool, str]:
    """
    Upload a signature image to R2.
    Stored at: signatures/{username}/{filename}
    Returns (success, message_or_url).
    """
    key = f"signatures/{username}/{filename}"
    try:
        client = _get_client()
        client.put_object(
            Bucket=_bucket(),
            Key=key,
            Body=io.BytesIO(file_bytes),
            ContentType=_content_type(filename),
        )
        return True, f"Signature uploaded: {key}"
    except NoCredentialsError:
        return False, "R2 credentials are missing or invalid."
    except ClientError as e:
        return False, f"R2 upload error: {e}"
    except Exception as e:
        return False, f"Unexpected error: {e}"


def upload_pdf(username: str, file_bytes: bytes, filename: str) -> tuple[bool, str]:
    """
    Upload an original PDF document to R2.
    Stored at: pdfs/{username}/{filename}
    Returns (success, message_or_key).
    """
    key = f"pdfs/{username}/{filename}"
    try:
        client = _get_client()
        client.put_object(
            Bucket=_bucket(),
            Key=key,
            Body=io.BytesIO(file_bytes),
            ContentType="application/pdf",
        )
        return True, key
    except NoCredentialsError:
        return False, "R2 credentials are missing or invalid."
    except ClientError as e:
        return False, f"R2 upload error: {e}"
    except Exception as e:
        return False, f"Unexpected error: {e}"


def upload_signed_pdf(username: str, file_bytes: bytes, filename: str) -> tuple[bool, str]:
    """
    Upload a signed PDF to R2.
    Stored at: signed_pdfs/{username}/{filename}
    Returns (success, message_or_key).
    """
    key = f"signed_pdfs/{username}/{filename}"
    try:
        client = _get_client()
        client.put_object(
            Bucket=_bucket(),
            Key=key,
            Body=io.BytesIO(file_bytes),
            ContentType="application/pdf",
        )
        return True, key
    except NoCredentialsError:
        return False, "R2 credentials are missing or invalid."
    except ClientError as e:
        return False, f"R2 upload error: {e}"
    except Exception as e:
        return False, f"Unexpected error: {e}"


def list_user_files(username: str, category: str) -> list[dict]:
    """
    List files for a user in the given category folder.
    category: 'signatures' | 'pdfs' | 'signed_pdfs'
    Returns list of dicts with keys: name, key, size, last_modified.
    """
    prefix = f"{category}/{username}/"
    try:
        client = _get_client()
        resp = client.list_objects_v2(Bucket=_bucket(), Prefix=prefix)
        items = []
        for obj in resp.get("Contents", []):
            key = obj["Key"]
            name = key[len(prefix):]  # strip prefix to get just the filename
            if not name:
                continue
            items.append({
                "name": name,
                "key": key,
                "size": obj.get("Size", 0),
                "last_modified": obj.get("LastModified"),
            })
        # newest first
        items.sort(key=lambda x: x["last_modified"] or "", reverse=True)
        return items
    except Exception:
        return []


def download_file(key: str) -> bytes | None:
    """Download a file from R2 by its key. Returns bytes or None on error."""
    try:
        client = _get_client()
        resp = client.get_object(Bucket=_bucket(), Key=key)
        return resp["Body"].read()
    except Exception:
        return None


def r2_is_configured() -> bool:
    """Return True if all R2 environment variables are set."""
    return all([
        os.environ.get("R2_ACCESS_KEY_ID"),
        os.environ.get("R2_SECRET_ACCESS_KEY"),
        os.environ.get("R2_ENDPOINT_URL"),
    ])


def _content_type(filename: str) -> str:
    ext = filename.lower().rsplit(".", 1)[-1]
    return {
        "png":  "image/png",
        "jpg":  "image/jpeg",
        "jpeg": "image/jpeg",
    }.get(ext, "application/octet-stream")
