import asyncio
from functools import reduce

import vlc


def vlc_flags_or_internal(acc: int, val):
    return acc | val.value


def vlc_flags_or(*args):
    return reduce(
        vlc_flags_or_internal,
        args,
        0,
    )


def wrap_vlc_event(ev: vlc.EventType, event: vlc.Event):
    loop = asyncio.get_event_loop()
    f = loop.create_future()

    def cb():
        try:
            f.set_result(None)
        except asyncio.exceptions.InvalidStateError:
            # Future is already done :idk
            pass

        ev.event_detach(event)

    ev.event_attach(
        event,
        lambda event: loop.call_soon_threadsafe(cb),
    )
    return f
