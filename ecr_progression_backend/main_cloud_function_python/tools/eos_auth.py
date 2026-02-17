"""
Checks EOS authentication token according to the documentation:
https://dev.epicgames.com/docs/epic-account-services/auth/auth-interface
Validating ID Tokens on Backend Without SDK

To retrieve epic account id with EOS in UE, use
IOnlineSubsystem::Get()->GetIdentityInterface()->GetUniquePlayerId(0).ToString()
then extract part before "|".

To retrieve auth token in UE, use
IOnlineSubsystem::Get()->GetIdentityInterface()->GetAuthToken(0)
"""
import logging
import time
import traceback

import requests
import jwt
import json
import os
import sys


# Default token max age: 72 hours (dirty fix around OnlineSubsystemEOS not being able to return refreshed token)
DEFAULT_MAX_TOKEN_AGE = 72 * 60 * 60


class EOSAuthVerifier:
    def __init__(self, logger):
        self.logger = logger

        self.public_keys = {}

        if os.path.exists("/tmp/"):
            self.eos_keys_fp = "/tmp/eos_keys.json"
        else:
            self.eos_keys_fp = ""

        if os.path.exists(self.eos_keys_fp):
            with open(self.eos_keys_fp, "r") as f:
                latest_key_data_cache = json.load(f)
        else:
            latest_key_data_cache = {
                "keys": [
                    {
                        "kty": "RSA",
                        "e": "AQAB",
                        "kid": "WMS7EnkIGpcH9DGZsv2WcY9xsuFnZCtxZjj4Ahb-_8E",
                        "n": "l6XI48ujknQQlsJgpGXg4l2i_DuUxuG2GXTzkOG7UtX4MqkVBCfW1t1JIIc8q0kCInC2oBwhC599ZCmd-cOi0kS7Aquv68fjERIRK9oCUnF_lJg296jV8xcalFY0FOWX--qX3xGKL33VjJBMIrIu7ETjj06s-v4li22CnHmu2lDkrp_FPTVzFscn-XRIojqIFb7pKRFPt27m12FNE_Rd9bqlVCkvMNuE7VTpTOrSfKk5B01M5IuXKXk0pTAWnelqaD9bHjAExe2I_183lp_uFhNN4hLTjOojxl-dK8Jy2OCPEAsg5rs9Lwttp3zZ--y0sM7UttN2dE0w3F2f352MNQ"
                    }
                ]
            }

        self.__refresh_keys_from_key_data(latest_key_data_cache)

        self.issuer_start_string = "https://api.epicgames.dev"
        # Set environmental variable according to your EOS app Client Id
        # If you did set up EOS correctly, it will be in Project Settings, Plugins, Online Subsystem EOS, Artifacts
        self.client_id = os.getenv("EOS_CLIENT_ID")

    def __refresh_keys_from_key_data(self, key_data):
        self.public_keys = {}
        for jwk in key_data["keys"]:
            kid = jwk['kid']
            self.public_keys[kid] = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))

    def __drop_cached_keys_and_get_latest(self):
        r = requests.get("https://api.epicgames.dev/epic/oauth/v2/.well-known/jwks.json")
        latest_key_data = r.json()

        if self.eos_keys_fp:
            with open(self.eos_keys_fp, "w") as f:
                json.dump(latest_key_data, f)
        self.__refresh_keys_from_key_data(latest_key_data)

    def validate_token(self, account_id, token):
        try:
            header_data = jwt.get_unverified_header(token)

            alg = header_data.get("alg")
            kid = header_data.get("kid")

            # Step 1: alg is present and not None
            if not alg:
                raise ValueError("Alg header is None")
            if not kid:
                raise ValueError("Kid header is None")

            if kid not in self.public_keys:
                self.__drop_cached_keys_and_get_latest()
                if kid not in self.public_keys:
                    raise ValueError(f"Kid {kid} not found in keys")

            public_key = self.public_keys[kid]
            # Here it checks key (step 2), expiration (step 5), audience (step 6)
            payload = jwt.decode(
                token,
                key=public_key,
                algorithms=[header_data['alg']],
                audience=self.client_id,
                options={
                    "verify_exp": False,  # 🔴 disable built-in expiration check
                }
            )

            # Check issuer (step 3)
            issuer = payload.get("iss", "")
            if not issuer.startswith(self.issuer_start_string):
                raise ValueError(f"Bad issuer: {issuer}")

            # Check that iat is in the past (step 4)
            iat = payload.get("iat")
            now = int(time.time())
            if not isinstance(iat, int):
                raise ValueError(f"Non-number iat: {iat}")
            if not (iat < now):
                raise ValueError(f"Iat is not before current time: {iat}")

            # Check expiration (step 5)
            if now - iat > DEFAULT_MAX_TOKEN_AGE:
                raise ValueError(
                    f"Token expired by custom policy: age={now - iat}s max={DEFAULT_MAX_TOKEN_AGE}s"
                )

            # Check that account in token is same as specified in request
            token_account_id = payload.get("sub", "")
            if account_id != token_account_id:
                raise ValueError(f"Account id {account_id} didn't match with token account id {token_account_id}")

            return True

        except Exception as e:
            self.logger.error(f"Couldn't validate token {token} for id {account_id}\n\n{traceback.format_exc(limit=2)}")
            return False


if __name__ == '__main__':
    s = EOSAuthVerifier(logging.getLogger(__name__))
    with open("../eos_token_example.txt", "r") as f:
        token = f.read()
    with open("../eos_token_account_id.txt", "r") as f:
        account_id = f.read()
    print(s.validate_token(account_id, token))
