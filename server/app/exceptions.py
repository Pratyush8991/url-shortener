from app.config import ATTEMPT_CAP

class AliasAlreadyExistsError(Exception):
    def __init__(self, alias: str):
        self.alias = alias
        super().__init__(f"Alias '{alias}' already exists")

class UrlNotFoundError(Exception):
    def __init__(self, url: str):
        super().__init__(f"URL - {url} not found.")

class UrlExpiredError(Exception):
    def __init__(self, url: str):
        super().__init__(f"URL - {url} expired.")

class ShortCodeExhaustionError(Exception):
    def __init__(self, original_url: str):
        super().__init__(f"Could not allocate a short code for {original_url} after {ATTEMPT_CAP} attempts.")