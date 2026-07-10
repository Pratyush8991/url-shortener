from abc import ABC, abstractmethod

class UrlCreationStrategy(ABC):
    @abstractmethod
    def create_short_code(self, original_url: str, attempt: int) -> str:
        pass
