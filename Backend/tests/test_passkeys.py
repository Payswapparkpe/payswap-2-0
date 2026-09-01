import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from accounts.services import PasskeyService


@pytest.mark.django_db
class TestPasskeys:
    def test_register_and_authenticate(self, merchant_user):
        session = {}
        challenge = PasskeyService.issue_challenge(session)
        private = Ed25519PrivateKey.generate()
        public_pem = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
        cred = PasskeyService.register(
            merchant_user,
            session=session,
            credential_id="cred-1",
            public_key_hex=public_pem,
            challenge=challenge,
        )
        assert cred.credential_id == "cred-1"
        challenge2 = PasskeyService.issue_challenge(session)
        signature = private.sign(challenge2.encode()).hex()
        assert PasskeyService.authenticate(
            merchant_user,
            session=session,
            credential_id="cred-1",
            signature_hex=signature,
            challenge=challenge2,
        )

    def test_wrong_signature_fails(self, merchant_user):
        session = {}
        challenge = PasskeyService.issue_challenge(session)
        private = Ed25519PrivateKey.generate()
        public_pem = private.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw).hex()
        PasskeyService.register(
            merchant_user,
            session=session,
            credential_id="cred-2",
            public_key_hex=public_pem,
            challenge=challenge,
        )
        challenge2 = PasskeyService.issue_challenge(session)
        assert (
            PasskeyService.authenticate(
                merchant_user,
                session=session,
                credential_id="cred-2",
                signature_hex="00" * 64,
                challenge=challenge2,
            )
            is False
        )
