from typing import List
import aiohttp
import logging
import os
import asyncio
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCConfiguration, RTCIceServer
from aiortc.contrib.media import MediaRecorder, MediaRelay
from ..logger import setup_logger

# Set up the logger with color and timestamp support
logger = setup_logger(name=__name__, log_level=logging.INFO)

DEFAULT_HEYGEN_URL = "https://api.heygen.com"

def _get_ice_servers(ice_servers_list) -> List[RTCIceServer]:
    _ice_servers = list()
    for ice_server in ice_servers_list:
        logger.info(f"Adding ice server: {ice_server}")
        _ice_servers.append(RTCIceServer(
            urls=ice_server["urls"],
            username=ice_server.get("username") or None,
            credential=ice_server.get("credential") or None,
            credentialType=ice_server.get("credentialType")
        ))
    return _ice_servers


class StreamingApiConnection:
    def __init__(
        self, api_key: str = None, 
        base_url: str = DEFAULT_HEYGEN_URL
    ):
        self.api_key = api_key or os.environ.get("HEYGEN_API_KEY")
        self.base_url = base_url
        self.session_info = None
        self.peer_connection = None
        self.session = aiohttp.ClientSession()
        self.recorder = MediaRecorder('./myfile.mp4')
        self.relay = MediaRelay()

    async def create_new_session(self, callback):
        logger.debug("Creating new session.")

        url = f"{self.base_url}/v1/streaming.new"

        payload = {
            "quality": "medium",
            "voice": {"rate": 1},
            "video_encoding": "VP8",
            "disable_idle_timeout": False,
        }
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "x-api-key": self.api_key,
        }

        response = await self.session.post(url, json=payload, headers=headers)

        data = await response.json()
        self.session_info = data["data"]

        ice_servers = _get_ice_servers(self.session_info["ice_servers2"])

        configuration = RTCConfiguration(iceServers=ice_servers)

        self.peer_connection = RTCPeerConnection(
            configuration=configuration
        )

        @self.peer_connection.on("track")
        def on_track(track):
            logger.info(f"Received {track.kind} track: {track.id}")
            if track.kind == "video":
                self.recorder.addTrack(self.relay.subscribe(track))
                callback(track)
            elif track.kind == "audio":
                self.recorder.addTrack(track)
                logger.debug("Ignoring non video track")

            @track.on("ended")
            async def on_ended():
                logger.info(f"{track.kind} track {track.id} ended")
                await self.recorder.stop()

        
        remote_description = RTCSessionDescription(
            sdp=self.session_info["sdp"]["sdp"], 
            type=self.session_info["sdp"]["type"]
        )

        try:
            await self.peer_connection.setRemoteDescription(
                sessionDescription=remote_description
            )
            await self.recorder.start()
        except:
            logger.error("Failed to set remote description")

    async def start_streaming_session(self):
        logger.debug("Starting streaming session.")

        url = f"{self.base_url}/v1/streaming.start"

        local_description = await self.peer_connection.createAnswer()
        await self.peer_connection.setLocalDescription(local_description)

        payload = {
            "session_id": self.session_info["session_id"],
            "sdp": {"type": "answer", "sdp": local_description.sdp},
        }

        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "x-api-key": self.api_key,
        }

        await self.session.post(url, json=payload, headers=headers)

    async def send_text(self, text: str):
        logger.debug("Sending text", text)

        url = f"{self.base_url}/v1/streaming.task"

        payload = {
            "session_id": self.session_info["session_id"],
            "text": text
        }
        headers = {
            "accept": "application/json",
            "content-type": "application/json",
            "x-api-key": self.api_key,
        }

        await self.session.post(url, json=payload, headers=headers)

    async def close_session(self):
        logger.debug("Closing session.")

        url = f"{self.base_url}/v1/streaming.stop"

        payload  = {
            "session_id": self.session_info["session_id"],
         }

        headers  = {
             "accept": "application/json",
             "content-type": "application/json",
             "x-api-key": self.api_key,
        }

        await self.session.post(url, json=payload, headers=headers)
