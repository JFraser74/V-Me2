# Minimal shim for python-multipart used during tests
# This provides only the name so import doesn't fail; fastapi will still
# complain if features are required at runtime, but many tests run in fake mode.

class MultipartFormData:
    pass

# Expose a minimal API name
__all__ = ['MultipartFormData']
