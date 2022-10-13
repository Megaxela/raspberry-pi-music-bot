import re
import json
import logging
import typing as tp
import argparse
import asyncio
import sys

import aiohttp

logger = logging.getLogger(__name__)

URL_MATCH_RE = re.compile(r"youtube\.com\/playlist\?list=(?P<playlist_id>.*)$")


class YoutubePlaylistClient:
    def __init__(self):
        self._videos_json_paths = (
            (
                "contents",
                "twoColumnBrowseResultsRenderer",
                "tabs",
                "tabRenderer",
                "content",
                "sectionListRenderer",
                "contents",
                "itemSectionRenderer",
                "contents",
                "playlistVideoListRenderer",
                "contents",
            ),
            (
                "onResponseReceivedActions",
                "appendContinuationItemsAction",
                "continuationItems",
            ),
        )

    async def is_playlist(self, url: str) -> bool:
        return bool(URL_MATCH_RE.search(url))

    def _convert_video_ids(self, video_ids: tp.List[str]):
        return [f"https://www.youtube.com/watch?v={i}" for i in video_ids]

    def _find_jsons(self, data: str) -> list:
        result = []

        start_parentheses = {"{", "["}
        end_parentheses = {"}", "]"}
        is_in_string = False

        depth = 0
        json_begin = None

        for symbol_index in range(len(data)):
            if data[symbol_index] == '"':
                is_in_string = not is_in_string
            elif data[symbol_index] in start_parentheses:
                if is_in_string:
                    continue
                if depth == 0:
                    json_begin = symbol_index
                depth += 1
            elif data[symbol_index] in end_parentheses:
                if is_in_string:
                    continue
                if depth == 0:
                    continue

                depth -= 1

                if depth == 0:
                    # Trying to parse this "json"
                    sub_data = data[json_begin : symbol_index + 1]
                    try:
                        result.append(json.loads(sub_data))
                    except Exception:
                        # Trying to read inside data
                        sub_data = self._find_jsons(sub_data[1:])
                        if sub_data:
                            result += sub_data

        return result

    def _get_path(self, data, path) -> list:
        element = data
        for path_index in range(len(path)):
            if isinstance(element, list):
                result = list(
                    filter(
                        lambda x: x is not None,
                        [
                            self._get_path(array_element, path[path_index:])
                            for array_element in element
                        ],
                    )
                )
                return None if not result else result
            elif isinstance(element, dict):
                if path[path_index] not in element:
                    return None
                element = element[path[path_index]]
            else:
                # Unable to search in string, numbers etc
                return None
        return element

    def _try_load_videos(self, data):
        videos = None
        for path in self._videos_json_paths:
            result = self._get_path(data, path)
            if result is not None:
                videos = result
                break

        if videos is None:
            return None

        # Shrink it until more that 1 element
        while True:
            if len(videos) > 1 or not isinstance(videos, list):
                break
            videos = videos[0]

        continuation_token = None
        continuation_url = None
        results = set()
        for record in videos:
            video_id = record.get("playlistVideoRenderer", dict()).get("videoId")
            if video_id is not None:
                results.add(video_id)

            continuation_token_opt = (
                record.get("continuationItemRenderer", dict())
                .get("continuationEndpoint", dict())
                .get("continuationCommand", dict())
                .get("token")
            )
            if continuation_token_opt is not None:
                continuation_token = continuation_token_opt

            continuation_url_opt = (
                record.get("continuationItemRenderer", dict())
                .get("continuationEndpoint", dict())
                .get("commandMetadata", dict())
                .get("webCommandMetadata", dict())
                .get("apiUrl")
            )
            if continuation_url_opt is not None:
                continuation_url = continuation_url_opt

        return results, continuation_token, continuation_url

    def _try_load_key(self, data):
        if not isinstance(data, dict):
            return None
        return data.get("INNERTUBE_API_KEY")

    def _build_continuation_request_body(self, playlist_url, continuation_token):
        return {
            "context": {
                "client": {
                    "hl": "en",
                    "gl": "RU",
                    # "remoteHost": "5.39.166.200",
                    "deviceMake": "",
                    "deviceModel": "",
                    "visitorData": "Cgs2MnFMTTZTLTRsRSjFwt-WBg%3D%3D",
                    "userAgent": "Mozilla/5.0 (X11; Linux x86_64; rv:101.0) Gecko/20100101 Firefox/101.0,gzip(gfe)",
                    "clientName": "WEB",
                    "clientVersion": "2.20220719.01.00",
                    "osName": "X11",
                    "osVersion": "",
                    "originalUrl": playlist_url,
                    "platform": "DESKTOP",
                    "clientFormFactor": "UNKNOWN_FORM_FACTOR",
                    "configInfo": {},
                    "browserName": "Firefox",
                    "browserVersion": "101.0",
                    "screenWidthPoints": 1676,
                    "screenHeightPoints": 191,
                    "screenPixelDensity": 2,
                    "screenDensityFloat": 1.5,
                    "utcOffsetMinutes": 180,
                    "userInterfaceTheme": "USER_INTERFACE_THEME_LIGHT",
                    "mainAppWebInfo": {
                        "graftUrl": playlist_url,
                        "webDisplayMode": "WEB_DISPLAY_MODE_BROWSER",
                        "isWebNativeShareAvailable": False,
                    },
                    "timeZone": "Europe/Moscow",
                },
                "user": {"lockedSafetyMode": False},
                "request": {
                    "useSsl": True,
                    "internalExperimentFlags": [],
                    "consistencyTokenJars": [],
                },
                "clickTracking": {
                    "clickTrackingParams": "CCMQ7zsYACITCLjr34iph_kCFRp3mwod4dEKSw=="
                },
                "adSignalsInfo": {"params": []},
            },
            "continuation": continuation_token,
        }

    async def parse_media(self, url: str) -> tp.List[str]:
        url_match = URL_MATCH_RE.search(url)
        if not url_match:
            raise ValueError(f"String '{url}' is not an youtube playlist")

        playlist_id = url_match["playlist_id"]

        logger.info("Parsing '%s' playlist, with id '%s'", url, playlist_id)

        # Requesting youtube playlist page
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                data = await response.text()

        # Fetching jsons from page
        page_jsons = self._find_jsons(data)

        logger.debug("Found %d jsons in initial request to '%s'", len(page_jsons), url)

        total_videos = []

        # Parsing found jsons for desired data
        key = None
        continuation_url = None
        token = None
        for json_dict in page_jsons:
            videos_opt = self._try_load_videos(json_dict)
            if videos_opt is not None:
                videos, token, continuation_url = videos_opt
                total_videos += videos

            key_opt = self._try_load_key(json_dict)
            if key_opt is not None:
                key = key_opt

        logger.debug(
            "Initial jsons parsing gave: key: '%s', url: '%s', token: '%s'",
            key,
            continuation_url,
            token,
        )

        if token is None:
            if not total_videos:
                raise RuntimeError(f"Probably '{url}' has no available music inside")
            return self._convert_video_ids(total_videos)

        if continuation_url is None:
            raise RuntimeError(f"Unable to fetch continuation url for '{url}'")

        if key is None:
            raise RuntimeError(f"Unable to find playlist key for '{url}'")

        # Fetching remaining videos
        async with aiohttp.ClientSession() as session:
            while True:
                async with session.post(
                    f"https://www.youtube.com{continuation_url}?key={key}&prettyPrint=false",
                    headers={
                        "Content-Type": "application/json",
                    },
                    data=json.dumps(
                        self._build_continuation_request_body(
                            playlist_url=url,
                            continuation_token=token,
                        )
                    ),
                ) as response:
                    data = await response.json()

                videos_opt = self._try_load_videos(data)
                if videos_opt is None:
                    break
                videos, token, continuation_url = videos_opt

                total_videos += videos

                if token is None or url is None:
                    logger.debug("Seems like it's end of playlist '%s'", url)
                    break

        return self._convert_video_ids(total_videos)


def parse_args():
    args = argparse.ArgumentParser()

    args.add_argument("playlist")

    return args.parse_args()


async def main(args):
    client = YoutubePlaylistClient()

    if not (await client.is_playlist(args.playlist)):
        print(f"Url '{args.playlist}' is not a playlist")
        sys.exit(1)

    urls = await client.parse_media(args.playlist)
    if not urls:
        print(f"Unable to parse playlist '{args.playlist}'")
        sys.exit(2)

    list(map(print, urls))


if __name__ == "__main__":
    asyncio.new_event_loop().run_until_complete(main(parse_args()))
