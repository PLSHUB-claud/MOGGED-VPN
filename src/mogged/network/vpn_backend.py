from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional

class VPNBackend(ABC):

    @abstractmethod
    def connect(
        self,
        server: Dict[str, Any],
        mode: str = "full",
        on_status: Optional[Callable[[str, str], None]] = None,
    ) -> bool:
        pass

    @abstractmethod
    def disconnect(self) -> None:
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        pass
