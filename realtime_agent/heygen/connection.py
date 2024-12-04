import requests
import logging
import asyncio
from aiortc import RTCPeerConnection
from ..logger import setup_logger

# Set up the logger with color and timestamp support
logger = setup_logger(name=__name__, log_level=logging.INFO)

DEFAULT_HEYGEN_URL = "https://api.heygen.com"


class StreamingApiConnection:
    def __init__(self, api_key: str = None, base_url: str = DEFAULT_HEYGEN_URL):
        self.api_key = api_key
        self.base_url = base_url
        self.session_info = None
        self.peer_connection = None

    async def create_new_session(self):
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

        response = requests.post(url, json=payload, headers=headers)

        data = response.json()
        self.session_info = data["session"]

        self.peer_connection = RTCPeerConnection(
            configuration={"iceServers": self.session_info["ice_servers2"]}
        )

        @self.peer_connection.on("track")
        def on_track(track):
            logger.debug("Track received")
            print("Track received", track.kind)

        await self.peer_connection.setRemoteDescription(
            sdp=self.session_info["sdp"], type="offer"
        )

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

        requests.post(url, json=payload, headers=headers)

    def send_text(self, text: str):
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

        requests.post(url, json=payload, headers=headers)

    def close_session(self):
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

        requests.post(url, json=payload, headers=headers)
