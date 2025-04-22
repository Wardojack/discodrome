import discord
from discord.ext import commands

import logging

from subsonic import Song, Album, Playlist, get_album_art_file

logger = logging.getLogger(__name__)



class SysMsg:
    ''' A class for sending system messages '''

    @staticmethod
    async def msg(ctx: commands.Context, header: str, message: str=None, thumbnail: str=None, *, ephemeral: bool=False) -> None:
        ''' Generic message function. Creates a message formatted as an embed '''

        # Handle message over character limit
        if message is not None and len(message) > 4096:
            message = message[:4093] + "..."

        embed = discord.Embed(color=discord.Color(0x50C470), title=header, description=message)
        file = discord.utils.MISSING



        # Attach a thumbnail if one was provided (as a local file)
        if thumbnail is not None:
            file = discord.File(thumbnail, filename="image.png")
            embed.set_thumbnail(url="attachment://image.png")

        await ctx.channel.send(embed=embed)

        # Attempt to send the message, up to 3 times
        # attempt = 0
        # while attempt < 3:
        #     try:
        #         if interaction.response.is_done():
        #             await interaction.followup.send(file=file, embed=embed, ephemeral=ephemeral)
        #             return
        #         else:
        #             await interaction.response.send_message(file=file, embed=embed, ephemeral=ephemeral)
        #             return
        #     except discord.NotFound:
        #         logger.warning("Attempt %d at sending a system message failed...", attempt+1)
        #         attempt += 1


    @staticmethod
    async def now_playing(ctx: commands.Context, song: Song) -> None:
        ''' Sends a message containing the currently playing song '''
        cover_art = await get_album_art_file(song.cover_id)
        desc = f"**{song.title}** - *{song.artist}*\n{song.album} ({song.duration_printable})"
        await __class__.msg(ctx, "Now Playing:", desc, cover_art)

    @staticmethod
    async def playback_ended(ctx: commands.Context) -> None:
        ''' Sends a message indicating playback has ended '''
        await __class__.msg(ctx, "Playback ended")

    @staticmethod
    async def disconnected(ctx: commands.Context) -> None:
        ''' Sends a message indicating the bot disconnected from voice channel '''
        await __class__.msg(ctx, "Disconnected from voice channel")

    @staticmethod
    async def starting_queue_playback(ctx: commands.Context) -> None:
        ''' Sends a message indicating queue playback has started '''
        await __class__.msg(ctx, "Started queue playback")

    @staticmethod
    async def stopping_queue_playback(ctx: commands.Context) -> None:
        ''' Sends a message indicating queue playback has stopped '''
        await __class__.msg(ctx, "Stopped queue playback")

    @staticmethod
    async def added_to_queue(ctx: commands.Context, song: Song) -> None:
        ''' Sends a message indicating the selected song was added to queue '''
        desc = f"**{song.title}** - *{song.artist}*\n{song.album} ({song.duration_printable})"
        cover_art = await get_album_art_file(song.cover_id)
        await __class__.msg(ctx, f"{ctx.author.display_name} added track to queue", desc, cover_art)

    @staticmethod
    async def added_album_to_queue(ctx: commands.Context, album: Album) -> None:
        ''' Sends a message indicating the selected album was added to queue '''
        desc = f"**{album.name}** - *{album.artist}*\n{album.song_count} songs ({album.duration} seconds)"
        cover_art = await get_album_art_file(album.cover_id)
        await __class__.msg(ctx, f"{ctx.author.display_name} added album to queue", desc, cover_art)

    @staticmethod
    async def added_playlist_to_queue(ctx: commands.Context, playlist: Playlist) -> None:
        ''' Sends a message indicating the selected playlist was added to queue '''
        desc = f"**{playlist.name}**\n{playlist.song_count} songs ({playlist.duration} seconds)"
        cover_art = await get_album_art_file(playlist.cover_id)
        await __class__.msg(ctx, f"{ctx.author.display_name} added playlist to queue", desc, cover_art)

    @staticmethod
    async def added_discography_to_queue(ctx: commands.Context, artist: str, albums: list[Album]) -> None:
        ''' Sends a message indicating the selected artist's discography was added to queue '''
        desc = f"**{artist}**\n{len(albums)} albums\n\n"
        cover_art = await get_album_art_file(albums[0].cover_id)
        for counter in range(len(albums)):
            album = albums[counter]
            desc += f"**{str(counter+1)}. {album.name}**\n{album.song_count} songs ({album.duration} seconds)\n\n" 
        await __class__.msg(ctx, f"{ctx.author.display_name} added discography to queue", desc, cover_art)

    @staticmethod
    async def queue_cleared(ctx: commands.Context) -> None:
        ''' Sends a message indicating a user cleared the queue '''
        await __class__.msg(ctx, f"{ctx.author.display_name} cleared the queue")

    @staticmethod
    async def skipping(ctx: commands.Context) -> None:
        ''' Sends a message indicating the current song was skipped '''
        await __class__.msg(ctx, "Skipped track", ephemeral=True)


class ErrMsg:
    ''' A class for sending error messages '''

    @staticmethod
    async def msg(ctx: commands.Context, message: str) -> None:
        ''' Generic message function. Creates an error message formatted as an embed '''
        embed = discord.Embed(color=discord.Color(0x50C470), title="Error", description=message)

        await ctx.channel.send(embed=embed)
        # if interaction.response.is_done():
        #     await interaction.followup.send(embed=embed, ephemeral=True)
        # else:
        #     await interaction.response.send_message(embed=embed, ephemeral=True)

    @staticmethod
    async def user_not_in_voice_channel(ctx: commands.Context) -> None:
        ''' Sends an error message indicating user is not in a voice channel '''
        await __class__.msg(ctx, "You are not connected to a voice channel.")

    @staticmethod
    async def bot_not_in_voice_channel(ctx: commands.Context) -> None:
        ''' Sends an error message indicating bot is connect to a voice channel '''
        await __class__.msg(ctx, "Not currently connected to a voice channel.")

    @staticmethod
    async def cannot_connect_to_voice_channel(ctx: commands.Context) -> None:
        ''' Sends an error message indicating bot is unable to connect to a voice channel '''
        await __class__.msg(ctx, "Cannot connect to voice channel.")

    @staticmethod
    async def queue_is_empty(ctx: commands.Context) -> None:
        ''' Sends an error message indicating the queue is empty '''
        await __class__.msg(ctx, "Queue is empty.")

    @staticmethod
    async def already_playing(ctx: commands.Context) -> None:
        ''' Sends an error message indicating that music is already playing '''
        await __class__.msg(ctx, "Already playing.")

    @staticmethod
    async def not_playing(ctx: commands.Context) -> None:
        ''' Sends an error message indicating nothing is playing '''
        await __class__.msg(ctx, "No track is playing.")



# Methods for parsing data to Discord structures
def parse_search_as_track_selection_embed(results: list[Song], query: str, page_num: int) -> discord.Embed:
    ''' Takes search results obtained from the Subsonic API and parses them into a Discord embed suitable for track selection '''

    options_str = ""

    # Loop over the provided search results
    for song in results:

        # Trim displayed tags to fit neatly within the embed
        tr_title = song.title
        tr_artist = song.artist
        tr_album = (song.album[:68] + "...") if len(song.album) > 68 else song.album

        # Only trim the longest tag on the first line
        top_str_length = len(song.title + " - " + song.artist)
        if top_str_length > 71:
            
            if tr_title > tr_artist:
                tr_title = song.title[:(68 - top_str_length)] + '...'
            else:
                tr_artist = song.artist[:(68 - top_str_length)] + '...'

        # Add each of the results to our output string
        options_str += f"**{tr_title}** - *{tr_artist}* \n*{tr_album}* ({song.duration_printable})\n\n"

    # Add the current page number to our results
    options_str += f"Current page: {page_num}"

    # Return an embed that displays our output string
    return discord.Embed(color=discord.Color.orange(), title=f"Results for: {query}", description=options_str)


def parse_search_as_track_selection_options(results: list[Song]) -> list[discord.SelectOption]:
    ''' Takes search results obtained from the Subsonic API and parses them into a Discord selection list for tracks '''

    select_options = []
    for i, song in enumerate(results):
        select_option = discord.SelectOption(label=f"{song.title}", description=f"by {song.artist}", value=i)
        select_options.append(select_option)

    return select_options
