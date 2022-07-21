import abc
import typing as tp


class BasicParser(abc.ABC):
    @abc.abstractmethod
    async def is_suitable(self, url: str) -> bool:
        pass

    @abc.abstractmethod
    async def parse_media(self, url: str) -> tp.List[str]:
        pass
