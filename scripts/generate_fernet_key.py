#!/usr/bin/env python3
"""Generate a Fernet key for APP_ENCRYPTION_KEY.

Usage:
  python scripts/generate_fernet_key.py

Prints a base64 Fernet key to stdout.
"""
from cryptography.fernet import Fernet

def main():
    print(Fernet.generate_key().decode())

if __name__ == '__main__':
    main()
