import dataclasses
import typing as tp

from multimedia.media import Media
from multimedia.player import PlayerState


AddToPlaylistCallback = tp.Callable[[str], tp.Awaitable[tp.List[Media]]]
ListPlaylistCallback = tp.Callable[[], tp.List[Media]]
CurrentMediaCallback = tp.Callable[[], tp.Optional[Media]]
CurrentPlayerStateCallback = tp.Callable[[], PlayerState]
PauseCallback = tp.Callable[[], None]
ResumeCallback = tp.Callable[[], None]
SkipCallback = tp.Callable[[], tp.Awaitable[None]]
SkipAllCallback = tp.Callable[[], tp.Awaitable[None]]
ShuffleCallback = tp.Callable[[], tp.Awaitable[None]]
GetVolumeCallback = tp.Callable[[], int]
SetVolumeCallback = tp.Callable[[int], None]
GetCursorCallback = tp.Callable[[], int]
SetCursorCallback = tp.Callable[[int], None]
GetLengthCallback = tp.Callable[[int], None]
GetSeekCallback = tp.Callable[[], int]
SetSeekCallback = tp.Callable[[int], None]


@dataclasses.dataclass()
class Callbacks:
    add_to_playlist: tp.Optional[AddToPlaylistCallback] = None
    list_playlist: tp.Optional[ListPlaylistCallback] = None
    current_media: tp.Optional[CurrentMediaCallback] = None
    current_player_state: tp.Optional[CurrentPlayerStateCallback] = None
    pause: tp.Optional[PauseCallback] = None
    resume: tp.Optional[ResumeCallback] = None
    skip: tp.Optional[SkipCallback] = None
    skipall: tp.Optional[SkipAllCallback] = None
    shuffle: tp.Optional[ShuffleCallback] = None
    get_volume: tp.Optional[GetVolumeCallback] = None
    set_volume: tp.Optional[SetVolumeCallback] = None
    get_cursor: tp.Optional[GetCursorCallback] = None
    set_cursor: tp.Optional[SetCursorCallback] = None
    get_length: tp.Optional[GetLengthCallback] = None
    get_seek: tp.Optional[GetSeekCallback] = None
    set_seek: tp.Optional[SetSeekCallback] = None
