import discord
import logging
from discord import app_commands
from discord.ext import commands
from typing import Literal

from random import randint 
import data
import copy
import subsonic
import ui
from asyncio import sleep

from discodrome import DiscodromeClient

logger = logging.getLogger(__name__)

class MusicCog(commands.Cog):
    ''' A Cog containing music playback commands '''

    bot : DiscodromeClient

    def __init__(self, bot: DiscodromeClient):
        self.bot = bot

    async def get_voice_client(self, ctx: commands.Context, *, should_connect: bool=False) -> discord.VoiceClient:
        ''' Returns a voice client instance for the current guild '''

        # Get the voice client for the guild
        voice_client = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)

        # Connect to a voice channel
        if voice_client is None and should_connect:
            try:
                voice_client = await ctx.author.voice.channel.connect()
            except AttributeError:
                await ui.ErrMsg.cannot_connect_to_voice_channel(ctx)

        return voice_client

    @commands.hybrid_command(name="play")
    # @app_commands.command(name="play", description="Plays a specified track, album or playlist")
    # @app_commands.describe(querytype="Whether what you're searching is a track, album or playlist", query="Enter a search query")
    # @app_commands.choices(querytype=[
    #     app_commands.Choice(name="Track", value="track"),
    #     app_commands.Choice(name="Album", value="album"),
    #     app_commands.Choice(name="Playlist", value="playlist"),
    # ])
    async def play(self, ctx: commands.Context, querytype: Literal['track','album','playlist']=None, query: str=None) -> None:
        ''' Play a track matching the given title/artist query '''

        # Check if user is in voice channel
        if ctx.author.voice is None:
            return await ui.ErrMsg.user_not_in_voice_channel(ctx)

        # Get a valid voice channel connection
        voice_client = await self.get_voice_client(ctx, should_connect=True)

        # Don't attempt playback if the bot is already playing
        if voice_client.is_playing() and query is None:
            return await ui.ErrMsg.already_playing(ctx)

        # Get the guild's player
        player = data.guild_data(ctx.guild.id).player

        # Check queue if no query is provided
        if query is None:

            # Display error if queue is empty & autoplay is disabled
            if player.queue == [] and data.guild_properties(ctx.guild.id).autoplay_mode == data.AutoplayMode.NONE:
                return await ui.ErrMsg.queue_is_empty(ctx)

            # Begin playback of queue
            await ui.SysMsg.starting_queue_playback(ctx)
            await player.play_audio_queue(ctx, voice_client)
            return

        # Check querytype is not blank
        if querytype is None:
            return await ui.ErrMsg.msg(ctx, "Please provide a query type.")

        # Check if the query is a track
        if querytype == "track":

            # Send our query to the subsonic API and retrieve a list of 1 song
            songs = await subsonic.search(query, artist_count=0, album_count=0, song_count=1)
            if songs == "Error":
                await ui.ErrMsg.msg(ctx, f"An api error has occurred and has been logged to console. Please contact an administrator.")
                return

            # Display an error if the query returned no results
            if len(songs) == 0:
                await ui.ErrMsg.msg(ctx, f"No track found for **{query}**.")
                return
            
            # Add the first result to the queue and handle queue playback
            player.queue.append(songs[0])

            await ui.SysMsg.added_to_queue(ctx, songs[0])

        elif querytype == "album":

            # Send query to subsonic API and retrieve a list of 1 album
            album = await subsonic.search_album(query)
            if album == None:
                await ui.ErrMsg.msg(ctx, f"No album found for **{query}**.")
                return
            
            # Add all songs from the album to the queue
            for song in album.songs:
                player.queue.append(song)
            
            await ui.SysMsg.added_album_to_queue(ctx, album)

        elif querytype == "playlist":

            # Send query to subsonic API and retrieve a list of all playlists
            playlists = await subsonic.get_user_playlists()
            if playlists == None:
                await ui.ErrMsg.msg(ctx, f"No playlists found.")
                return
            
            # Check if the specific playlist exists and get it's contents
            playlist = None
            playlist_id = None
            for playlist in playlists:
                if playlist["name"] == query:
                    playlist_id = playlist["id"]
                    break
            if playlist_id == None:
                await ui.ErrMsg.msg(ctx, f"No playlist found for **{query}**.")
                return
            else:
                playlist = await subsonic.get_playlist(playlist_id)
            if playlist == None:
                # If we end up here then the following error message doesn't really cover it... It's more likely an error in this code
                await ui.ErrMsg.msg(ctx, f"No playlist found for **{query}**.")
                return
            
            # Add all songs from the playlist to the queue
            for song in playlist.songs:
                player.queue.append(song)
            
            await ui.SysMsg.added_playlist_to_queue(ctx, playlist)

        await player.play_audio_queue(ctx, voice_client)

    @play.error
    async def play_error(self, ctx, error):
        if isinstance(error, subsonic.APIError):
            logging.error(f"An API error has occurred playing a track, code {error.code}: {error.message}")
            await ui.ErrMsg.msg(ctx, "An API error has occurred and has been logged to console. Please contact an administrator.")
        else:
            logging.error(f"An error occurred while playing a track: {error}")
            await ui.ErrMsg.msg(ctx, f"An unknown error has occurred and has been logged to console. Please contact an administrator. {error}")


    @commands.hybrid_command(name="stop")
    # @app_commands.command(name="stop", description="Stop playing the current track")
    async def stop(self, ctx: commands.Context) -> None:
        ''' Disconnect from the active voice channel '''

        player = data.guild_data(ctx.guild.id).player

        if player.current_song is None:
            ui.ErrMsg.not_playing(ctx)

        # Get the voice client instance for the current guild
        voice_client = await self.get_voice_client(ctx)

        # Check if our voice client is connected
        if voice_client is None:
            await ui.ErrMsg.bot_not_in_voice_channel(ctx)
            return

        # Stop playback
        voice_client.stop()

        player.current_song = None
        
        # Add current song back to the queue if exists
        player.queue.insert(0, player.current_song)

        # Display disconnect confirmation
        await ui.SysMsg.stopping_queue_playback(ctx)

    @stop.error
    async def stop_error(self, ctx, error):
        logging.error(f"An error occurred while stopping playback: {error}")
        await ui.ErrMsg.msg(ctx, f"An unknown error has occurred and has been logged to console. Please contact an administrator. {error}")


    @commands.hybrid_command(name="queue")
    # @app_commands.command(name="queue", description="View the current queue")
    async def show_queue(self, ctx: commands.Context) -> None:
        ''' Show the current queue '''

        # Get the audio queue for the current guild
        queue = data.guild_data(ctx.guild.id).player.queue

        # Create a string to store the output of our queue
        output = ""

        # Add currently playing song to output if available
        if data.guild_data(ctx.guild.id).player.current_song is not None:
            song = data.guild_data(ctx.guild.id).player.current_song
            output += f"**Now Playing:**\n{song.title} - *{song.artist}*\n{song.album} ({song.duration_printable})\n\n"

        # Loop over our queue, adding each song into our output string
        for i, song in enumerate(queue):
            strtoadd = f"{i+1}. **{song.title}** - *{song.artist}*\n{song.album} ({song.duration_printable})\n\n"
            if len(output+strtoadd) < 4083:
                output += strtoadd
            else:
                remaining = len(queue) - i
                output += f"**And {remaining} more...**"
                break

        # Check if our output string is empty & update it accordingly
        if output == "":
            output = "Queue is empty!"

        # Show the user their queue
        await ui.SysMsg.msg(ctx, "Queue", output)

    @show_queue.error
    async def show_queue_error(self, ctx, error):
        logging.error(f"An error occurred while displaying the queue: {error}")
        await ui.ErrMsg.msg(ctx, f"An unknown error has occurred and has been logged to console. Please contact an administrator. {error}")


    @commands.hybrid_command(name="clear")
    # @app_commands.command(name="clear", description="Clear the current queue")
    async def clear_queue(self, ctx: commands.Context) -> None:
        '''Clear the queue'''
        queue = data.guild_data(ctx.guild.id).player.queue
        queue.clear()

        # Let the user know that the queue has been cleared
        await ui.SysMsg.queue_cleared(ctx)

    @clear_queue.error
    async def clear_queue_error(self, ctx, error):
        logging.error(f"An error occurred while clearing the queue: {error}")
        await ui.ErrMsg.msg(ctx, f"An unknown error has occurred and has been logged to console. Please contact an administrator. {error}")


    @commands.hybrid_command(name="skip")
    # @app_commands.command(name="skip", description="Skip the current track")
    async def skip(self, ctx: commands.Context) -> None:
        ''' Skip the current track '''

        # Get the voice client instance
        voice_client = await self.get_voice_client(ctx)

        # Check if the bot is connected to a voice channel
        if voice_client is None:
            await ui.ErrMsg.bot_not_in_voice_channel(ctx)
            return

        # Check if the bot is playing music
        if not voice_client.is_playing():
            await ui.ErrMsg.not_playing(ctx)
            return

        await data.guild_data(ctx.guild.id).player.skip_track(ctx, voice_client)

    @skip.error
    async def skip_error(self, ctx, error):
        logging.error(f"An error occurred while skipping a track: {error}")
        await ui.ErrMsg.msg(ctx, f"An unknown error has occurred and has been logged to console. Please contact an administrator. {error}")


    @commands.hybrid_command(name="autoplay")
    # @app_commands.command(name="autoplay", description="Toggles autoplay")
    # @app_commands.describe(mode="Determines the method to use when autoplaying")
    # @app_commands.choices(mode=[
    #     app_commands.Choice(name="None", value="none"),
    #     app_commands.Choice(name="Random", value="random"),
    #     app_commands.Choice(name="Similar", value="similar"),
    # ])
    async def autoplay(self, ctx: commands.Context, mode: Literal['none', 'random', 'similar']) -> None:
        ''' Toggles autoplay '''

        logger.debug(f"Autoplay mode: {mode.value}")
        # Update the autoplay properties
        match mode.value:
            case "none":
                data.guild_properties(ctx.guild.id).autoplay_mode = data.AutoplayMode.NONE
            case "random":
                data.guild_properties(ctx.guild.id).autoplay_mode = data.AutoplayMode.RANDOM
            case "similar":
                data.guild_properties(ctx.guild.id).autoplay_mode = data.AutoplayMode.SIMILAR

        # Display message indicating new status of autoplay
        if mode.value == "none":
            await ui.SysMsg.msg(ctx, f"Autoplay disabled by {ctx.author.display_name}")
        else:
            await ui.SysMsg.msg(ctx, f"Autoplay enabled by {ctx.author.display_name}", f"Autoplay mode: **{mode.name}**")


        # If the bot is connected to a voice channel and autoplay is enabled, start queue playback
        voice_client = await self.get_voice_client(ctx)
        logger.debug(f"Voice client: {voice_client}")
        if voice_client:
            logger.debug(f"Is playing: {voice_client.is_playing()}")
        if voice_client is not None and not voice_client.is_playing():        
            player = data.guild_data(ctx.guild.id).player

            logger.debug(f"Queue: {player.queue}")
            try:
                logger.debug(f"Current song: {player.current_song.title}")
            except AttributeError:
                logger.debug("No current song")
                
            logger.debug("Playing audio queue...")
            await player.play_audio_queue(ctx, voice_client)
        
    @autoplay.error
    async def autoplay_error(self, ctx, error):
        if isinstance(error, subsonic.APIError):
            logging.error(f"An API error has occurred while toggling autoplay, code {error.code}: {error.message}")
            await ui.ErrMsg.msg(ctx, "An API error has occurred and has been logged to console. Please contact an administrator.")
        else:
            logging.error(f"An error occurred while toggling autoplay: {error}")
            await ui.ErrMsg.msg(ctx, f"An unknown error has occurred and has been logged to console. Please contact an administrator. {error}")

    
    @commands.hybrid_command(name="shuffle")
    # @app_commands.command(name="shuffle", description="Shuffles the current queue")
    async def shuffle(self, ctx: commands.Context):
        ''' Randomize current queue using Fisher-Yates algorithm '''
        temporaryqueue = copy.deepcopy(data.guild_data(ctx.guild.id).player.queue)
        shuffledqueue = []
        while len(temporaryqueue) > 0:
            randomindex = randint(0, len(temporaryqueue) - 1)
            shuffledqueue.append(temporaryqueue.pop(randomindex))
        
        data.guild_data(ctx.guild.id).player.queue = shuffledqueue
        await ui.SysMsg.msg(ctx, "Queue shuffled!")

    @shuffle.error
    async def shuffle_error(self, ctx, error):
        logging.error(f"An error occurred while shuffling the queue: {error}")
        await ui.ErrMsg.msg(ctx, f"An unknown error has occurred and has been logged to console. Please contact an administrator. {error}")


    @commands.hybrid_command(name="disco")
    # @app_commands.command(name="disco", description="Plays the artist's entire discography")
    # @app_commands.describe(artist="The artist to play")
    async def disco(self, ctx: commands.Context, artist: str):
        ''' Play the artist's entire discography'''

        # Get a valid voice channel connection
        voice_client = await self.get_voice_client(ctx, should_connect=True)

        # Get the guild's player
        player = data.guild_data(ctx.guild.id).player

        # Send our query to the subsonic API and retrieve list of albums in artist's discography
        albums = await subsonic.get_artist_discography(artist)
        if albums == None:
            await ui.ErrMsg.msg(ctx, f"No discography found for **{artist}**.")
            return
        
        # Add all songs from the artist's discography to the queue
        for album in albums:
            for song in album.songs:
                player.queue.append(song)
        
        # Display a message that discography was added to the queue
        await ui.SysMsg.added_discography_to_queue(ctx, artist, albums)

        # Begin playback of queue
        await player.play_audio_queue(ctx, voice_client)

    @disco.error
    async def disco_error(self, ctx, error):
        if isinstance(error, subsonic.APIError):
            logging.error(f"An API error has occurred while playing an artist's discography, code {error.code}: {error.message}")
            await ui.ErrMsg.msg(ctx, "An API error has occurred and has been logged to console. Please contact an administrator.")
        else:
            logging.error(f"An error occurred while playing an artist's discography: {error}")
            await ui.ErrMsg.msg(ctx, f"An unknown error has occurred and has been logged to console. Please contact an administrator. {error}")


    @commands.hybrid_command(name="playlists")
    # @app_commands.command(name="playlists", description="List all playlists")
    async def list_playlists(self, ctx):
        # Send query to subsonic API and retrieve a list of all playlists
        playlists = await subsonic.get_user_playlists()
        if playlists == None:
            await ui.ErrMsg.msg(ctx, f"No playlists found.")
            return

        # Create a string to store the output
        output = ""

        # Loop over the list of playlists, adding each one into our output string
        for i, playlist in enumerate(playlists):
            strtoadd = f"{i+1}. **{playlist['name']}** \n{playlist['songCount']} songs - {(playlist['duration'] // 60):02d}m {(playlist['duration'] % 60):02d}s\n\n"
            if len(output+strtoadd) < 4083:
                output += strtoadd
            else:
                remaining = len(playlists) - i
                output += f"**And {remaining} more...**"
                break

        # Check if our output string is empty & update it accordingly
        if output == "":
            output = "No playlists found."

        # Show the user their queue
        await ui.SysMsg.msg(ctx, "Available playlists", output)

    @list_playlists.error
    async def playlists_error(self, ctx, error):
        if isinstance(error, subsonic.APIError):
            logging.error(f"An API error has occurred while fetching playlists, code {error.code}: {error.message}")
            await ui.ErrMsg.msg(ctx, "An API error has occurred and has been logged to console. Please contact an administrator.")
        else:
            logging.error(f"An error occurred while fetching playlists: {error}")
            await ui.ErrMsg.msg(ctx, f"An unknown error has occurred and has been logged to console. Please contact an administrator. {error}")


    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState) -> None:
        ''' Event called when a user's voice state changes '''

        # Check if the bot is connected to a voice channel
        voice_client = discord.utils.get(self.bot.voice_clients, guild=member.guild)

        # Check if the bot is connected to a voice channel
        if voice_client is None:
            return

        # Check if the bot is alone in the voice channel
        if len(voice_client.channel.members) == 1:
            logger.debug("Bot is alone in voice channel, waiting 10 seconds before disconnecting...")
            # Wait for 10 seconds
            await sleep(10)
            
            # Check again if there are still no users in the voice channel
            if len(voice_client.channel.members) == 1:
                # Disconnect the bot and clear the queue
                await voice_client.disconnect()
                player = data.guild_data(member.guild.id).player
                player.queue.clear()
                player.current_song = None
                logger.info("The bot has disconnected and cleared the queue as there are no users in the voice channel.")
            else:
                logger.debug("Bot is no longer alone in voice channel, aborting disconnect...")

async def setup(bot: DiscodromeClient):
    ''' Setup function for the music.py cog '''

    await bot.add_cog(MusicCog(bot))
