"""Thin wrapper so CI can call the signer without shell quoting games.

Usage: python3 tools/sign.py sign <in.apk> <out.apk> --key <pem> --cert <crt>
"""
import sys

from sign_apk.cli import main

if __name__ == "__main__":
    sys.argv = ["sign-apk"] + sys.argv[1:]
    main()
