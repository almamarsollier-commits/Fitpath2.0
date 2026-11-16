"""Pruebas locales del servicio privado S3, sin red ni credenciales."""

import io
import unittest
from unittest.mock import patch

from backend.fitpath import create_app
from backend.fitpath.services.s3_storage import (
    S3StorageSettings,
    StorageConfigurationError,
    StorageValidationError,
    create_s3_storage,
    get_s3_storage,
)


VALID_CONFIG = {
    "S3_BUCKET": "fitpath-private-tests",
    "S3_REGION": "us-east-1",
    "S3_PREFIX": "fitpath",
    "S3_ALLOWED_CONTENT_TYPES": "image/jpeg, application/pdf",
    "S3_MAX_UPLOAD_BYTES": "8",
    "S3_DOWNLOAD_TTL_SECONDS": "300",
}


class FakeS3Client:
    def __init__(self):
        self.uploads = []
        self.downloads = []
        self.deletions = []

    def upload_fileobj(self, file_object, bucket, key, ExtraArgs):
        self.uploads.append((file_object.read(), bucket, key, ExtraArgs))

    def generate_presigned_url(self, operation, Params, ExpiresIn):
        self.downloads.append((operation, Params, ExpiresIn))
        return "https://example.invalid/temporary-download"

    def delete_object(self, Bucket, Key):
        self.deletions.append((Bucket, Key))


class S3StorageTests(unittest.TestCase):
    def test_configuration_requires_explicit_private_policy(self):
        for missing in (
            "S3_BUCKET",
            "S3_REGION",
            "S3_ALLOWED_CONTENT_TYPES",
            "S3_MAX_UPLOAD_BYTES",
        ):
            with self.subTest(missing=missing):
                config = dict(VALID_CONFIG)
                config.pop(missing)
                with self.assertRaises(StorageConfigurationError):
                    S3StorageSettings.from_mapping(config)

    def test_upload_measures_content_and_never_sets_public_acl(self):
        client = FakeS3Client()
        service = create_s3_storage(VALID_CONFIG, client=client)
        key = service.upload_private(
            io.BytesIO(b"content"),
            namespace="clientes/1",
            content_type="application/pdf",
            content_length=7,
        )

        self.assertRegex(key, r"^fitpath/clientes/1/[0-9a-f]{32}$")
        data, bucket, uploaded_key, extra = client.uploads[0]
        self.assertEqual(data, b"content")
        self.assertEqual(bucket, "fitpath-private-tests")
        self.assertEqual(uploaded_key, key)
        self.assertEqual(
            extra,
            {"ContentType": "application/pdf", "ServerSideEncryption": "AES256"},
        )
        self.assertNotIn("ACL", extra)

    def test_upload_rejects_type_size_empty_and_mismatched_length(self):
        client = FakeS3Client()
        service = create_s3_storage(VALID_CONFIG, client=client)
        invalid_uploads = (
            (b"content", "text/plain", None),
            (b"too-large", "application/pdf", None),
            (b"", "application/pdf", None),
            (b"content", "application/pdf", 6),
        )
        for content, content_type, length in invalid_uploads:
            with self.subTest(content_type=content_type, length=length):
                with self.assertRaises(StorageValidationError):
                    service.upload_private(
                        io.BytesIO(content),
                        namespace="clientes/1",
                        content_type=content_type,
                        content_length=length,
                    )
        self.assertEqual(client.uploads, [])

    def test_download_url_is_short_lived_and_restricted_to_prefix(self):
        client = FakeS3Client()
        service = create_s3_storage(VALID_CONFIG, client=client)
        url = service.create_download_url("fitpath/clientes/1/opaque")
        self.assertEqual(url, "https://example.invalid/temporary-download")
        self.assertEqual(
            client.downloads,
            [
                (
                    "get_object",
                    {"Bucket": "fitpath-private-tests", "Key": "fitpath/clientes/1/opaque"},
                    300,
                )
            ],
        )
        with self.assertRaises(StorageValidationError):
            service.create_download_url("other/private-object")

    def test_delete_is_private_and_restricted_to_prefix(self):
        client = FakeS3Client()
        service = create_s3_storage(VALID_CONFIG, client=client)
        service.delete_private("fitpath/clientes/1/old-profile")
        self.assertEqual(
            client.deletions,
            [("fitpath-private-tests", "fitpath/clientes/1/old-profile")],
        )
        with self.assertRaises(StorageValidationError):
            service.delete_private("other/foreign-object")

    def test_flask_service_is_lazy_and_scoped_to_the_app_context(self):
        app = create_app("testing", dict(VALID_CONFIG, SECRET_KEY="test-only"))
        fake_client = FakeS3Client()
        with patch("backend.fitpath.services.s3_storage.boto3.client", return_value=fake_client):
            with app.app_context():
                first = get_s3_storage()
                second = get_s3_storage()
                self.assertIs(first, second)
        self.assertEqual(fake_client.uploads, [])


if __name__ == "__main__":
    unittest.main()
