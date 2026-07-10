"""
1. Canonicalize the original URL
2. SHA 256 hash the above - Need to encode string into bytes before hashing it. Use utf-8 to encode it. 
Or simply just use the b literal in front of the string to automatically instantiate it as byte literal.
3. base62 encode it
4. Take the first 6 words and return the result
"""
import hashlib
import base62
from app.strategies.base import UrlCreationStrategy


class HashUrlCreationStrategy(UrlCreationStrategy):
    def create_short_code(self, original_url: str, attempt: int = 0) -> str:
        hash_digest = hashlib.sha256((f"{original_url}#{attempt}").encode('utf-8')).digest()
        hash_number = int.from_bytes(hash_digest, byteorder="big")
        short_code = base62.encode(hash_number)[:6]

        return short_code
