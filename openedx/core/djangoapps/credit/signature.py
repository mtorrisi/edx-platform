"""
TODO: more description here.

Requests to and from the credit provider will be digitally signed as follows:

1) Encode all parameters of the request (except the signature) in a string.
2) Encode each key/value pair as a string of the form "{key}:{value}".
3) Concatenate key/value pairs in ascending alphabetical order by key.
4) Calculate the HMAC-SHA256 digest of the encoded request parameters, using a 32-character shared secret key.
5) Encode the digest in hexadecimal.
"""

import hashlib
import hmac


def signature(params, shared_secret):
    """
    TODO
    """
    encoded_params = "".join([
        "{key}:{value}".format(key=key, value=params[key])
        for key in sorted(params.keys())
        if key != "signature"
    ])
    h = hmac.new(shared_secret, encoded_params, hashlib.sha256)
    return h.hexdigest()
