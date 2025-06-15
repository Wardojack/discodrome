''' A player object that handles playback and data for its respective guild '''

import asyncio
import discord

import data
import ui
import logging

from subsonic import Song, APIError, get_random_songs, get_similar_songs, stream

logger = logging.getLogger(__name__)

# Default player data
_default_data: dict[str, any] = {
    "current-song": None,
    "current-position": 0,
    "queue": [],
}

class Player():
    ''' Class that represents an audio player '''
    def __init__(self) -> None:
        self._data = _default_data  
        self._player_loop = None

    @property
    def current_song(self) -> Song:
        '''The current song'''
        return self._data["current-song"]

    @current_song.setter
    def current_song(self, song: Song) -> None:
        self._data["current-song"] = song

    @property
    def current_position(self) -> int:
        ''' The current position for the current song, in seconds. '''
        return self._data["current-position"]

    @current_position.setter
    def current_position(self, position: int) -> None:
        ''' Set the current position for the current song, in seconds. '''
        self._data["current-position"] = position

    @property
    def queue(self) -> list[Song]:
        ''' The current audio queue. '''
        return self._data["queue"]

    @queue.setter
    def queue(self, value: list) -> None:
        self._data["queue"] = value

    @property
    def player_loop(self) -> asyncio.AbstractEventLoop:
        ''' The player loop '''
        return self._player_loop
    
    @player_loop.setter
    def player_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._player_loop = loop





    async def stream_track(self, interaction: discord.Interaction, song: Song, voice_client: discord.VoiceClient) -> None:
        ''' Streams a track from the Subsonic server to a connected voice channel, and updates guild data accordingly '''

        # Make sure the voice client is available
        if voice_client is None:
            await ui.ErrMsg.bot_not_in_voice_channel(interaction)
            return

        # Make sure the bot isn't already playing music
        if voice_client.is_playing():
            await ui.ErrMsg.already_playing(interaction)
            return

        # Get the stream from the Subsonic server, using the provided song's ID
        ffmpeg_options = {"before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
                           "options": "-filter:a volume=replaygain=track"}
        try:
            audio_src = discord.FFmpegOpusAudio(await stream(song.song_id), **ffmpeg_options)
        except APIError as err:
            logging.error(f"API Error streaming song, Code {err.errorcode}: {err.message}")
        # audio_src.read()

        # TODO: Start a duration timer

        # Begin playing the song
        loop = asyncio.get_event_loop()
        self.player_loop = loop

        # Handle playback finished
        async def playback_finished(error):
            if error:
                logging.error(f"An error occurred while playing the audio: {error}")
                return
            logger.debug("Playback finished.")
            try:
                future = asyncio.run_coroutine_threadsafe(self.play_audio_queue(interaction, voice_client), loop)
                # Add a callback to handle any exceptions that occur during execution
                future.add_done_callback(lambda f: logger.error(f"Error in play_audio_queue: {f.exception()}") if f.exception() else None)
            except Exception as e:
                logging.error(f"Failed to schedule play_audio_queue: {e}")


        try:
            voice_client.play(audio_src, after=lambda e: loop.create_task(playback_finished(e)))
        except Exception as err:
            logging.error(f"An error occurred while playing the audio: {err}")
            return


    async def handle_autoplay(self, interaction: discord.Interaction, prev_song_id: str=None) -> bool:
        ''' Handles populating the queue when autoplay is enabled '''

        autoplay_mode = data.guild_properties(interaction.guild_id).autoplay_mode
        queue = data.guild_data(interaction.guild_id).player.queue
        logger.debug("Handling autoplay...")
        logger.debug(f"Autoplay mode: {autoplay_mode}")
        logger.debug(f"Queue: {queue}")
        # If queue is notempty or autoplay is disabled, don't handle autoplay
        if queue != [] or autoplay_mode is data.AutoplayMode.NONE:
            return False

        # If there was no previous song provided, we default back to selecting a random song
        if prev_song_id is None:
            autoplay_mode = data.AutoplayMode.RANDOM
            logging.info("No previous song ID provided. Defaulting to random.")

        songs = []

        try:
            match autoplay_mode:
                case data.AutoplayMode.RANDOM:
                    songs = await get_random_songs(size=1)
                case data.AutoplayMode.SIMILAR:
                    logger.debug(f"Prev song ID: {prev_song_id}")
                    songs = await get_similar_songs(song_id=prev_song_id, count=1)

        except APIError as err:
            logging.error(f"API Error fetching song for autoplay, Code {err.errorcode}: {err.message}")
        
        logger.debug(f"Autoplay song: {songs}")

        # If there's no match, throw an error
        if len(songs) == 0:
            await ui.ErrMsg.msg(interaction, "Failed to obtain a song for autoplay.")
            return False
        
        self.queue.append(songs[0])
        return True


    async def play_audio_queue(self, interaction: discord.Interaction, voice_client: discord.VoiceClient) -> None:
        ''' Plays the audio queue '''

        # Check if the bot is connected to a voice channel; it's the caller's responsibility to open a voice channel
        if voice_client is None:
            await ui.ErrMsg.bot_not_in_voice_channel(interaction)
            return
        
        # Check if the bot is already playing something
        if voice_client.is_playing():
            return


        # Check if the queue contains songs
        if self.queue != []:
            # Pop the first item from the queue and stream the track
            song = self.queue.pop(0)
            self.current_song = song
            await ui.SysMsg.now_playing(interaction, song)
            await self.stream_track(interaction, song, voice_client)
        else:
            logger.debug("Queue is empty.")
            logger.debug("Current song: %s", self.current_song)
            if self.current_song is not None:
                prev_song_id = self.current_song.song_id
                self.current_song = None
            else:
                prev_song_id = None
            # Handle autoplay if queue is empty
            if await self.handle_autoplay(interaction, prev_song_id=prev_song_id):
                await self.play_audio_queue(interaction, voice_client)
                return
            # If the queue is empty, playback has ended; we should let the user know
            await ui.SysMsg.playback_ended(interaction)


    async def skip_track(self, interaction: discord.Interaction, voice_client: discord.VoiceClient) -> None:
        ''' Skips the current track and plays the next one in the queue '''

        # Check if the bot is connected to a voice channel; it's the caller's responsibility to open a voice channel
        if voice_client is None:
            await ui.ErrMsg.bot_not_in_voice_channel(interaction)
            return
        logger.debug("Skipping track...")
        # Check if the bot is already playing something
        if voice_client.is_playing():
            voice_client.stop()
            await ui.SysMsg.skipping(interaction)
        else:
            await ui.ErrMsg.not_playing(interaction)


