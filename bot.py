import discord
from discord.ext import commands
import yt_dlp
import asyncio

import os

import imageio_ffmpeg
FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()

import discord

# Ruta al binario de Opus empaquetado
OPUS_LIB_PATH = os.path.join(os.path.dirname(__file__), "libopus.so.0")

if not discord.opus.is_loaded():
    try:
        discord.opus.load_opus(OPUS_LIB_PATH)
        print("✅ Opus cargado desde binario empaquetado")
    except Exception as e:
        print(f"❌ Error crítico: No se pudo cargar Opus: {e}")
        exit(1)
# Cargar .env solo si existe (para desarrollo local)
if os.path.exists(".env"):
    from dotenv import load_dotenv
    load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

if not TOKEN:
    raise ValueError(
        "❌ No se ha encontrado DISCORD_TOKEN. "
        "En local usa un archivo .env, en Railway configúralo en Variables de Entorno."
    )

# Opciones para videos individuales
ytdl_video_opts = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}

# Opciones para playlists
ytdl_playlist_opts = {
    'format': 'bestaudio/best',
    'extract_flat': True,  # Solo metadata, no descarga
    'quiet': True,
    'no_warnings': True,
    'skip_download': True,
    'playlistend': 50  # Máximo 50 canciones
}

ffmpeg_options = {
    'options': '-vn -bufsize 64k',
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'
}

ytdl_video = yt_dlp.YoutubeDL(ytdl_video_opts)
ytdl_playlist = yt_dlp.YoutubeDL(ytdl_playlist_opts)

class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_query(cls, query, *, loop=None, stream=True):
        """Acepta URL o término de búsqueda."""
        loop = loop or asyncio.get_event_loop()
        
        # Si no parece una URL, forzamos búsqueda en YouTube
        if not query.startswith(('http://', 'https://')):
            query = f"ytsearch:{query}"
        
        data = await loop.run_in_executor(None, lambda: ytdl_video.extract_info(query, download=False))
        
        if 'entries' in data:
            data = data['entries'][0]  # Primer resultado
        
        return cls(
            discord.FFmpegPCMAudio(
            data['url'],
            **ffmpeg_options,
            executable=FFMPEG_PATH,  # ← usa el FFmpeg empaquetado
            ),
            data=data
        )

# === Cola de reproducción simple ===
class MusicQueue:
    def __init__(self):
        self.queue = []
    
    def add(self, url_or_list):
        self.queue.extend(url_or_list)
    
    def next(self):
        return self.queue.pop(0) if self.queue else None
    
    def is_empty(self):
        return len(self.queue) == 0

# Instancia global (para simplicidad; en bots grandes usarías cogs)
music_queue = MusicQueue()

# Al inicio del archivo, después de music_queue
user_selections = {}  # {user_id: list_of_results}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

async def play_next(ctx):
     # Verifica que el bot siga conectado a un canal de voz
    if not ctx.voice_client or not ctx.voice_client.is_connected():
        music_queue.queue.clear()  # Limpia la cola si ya no está conectado
        return
    
    """Reproduce la siguiente canción en la cola."""
    if not music_queue.is_empty():
        next_url = music_queue.next()
        try:
            player = await YTDLSource.from_query(next_url, loop=bot.loop, stream=True)
            ctx.voice_client.play(
                player,
                after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop) if not e else print(f'Error: {e}')
            )
            await ctx.send(f'🎶 Ahora: **{player.title}**')
        except Exception as e:
            import traceback
            print("=== ERROR DETALLADO ===")
            traceback.print_exc()
            await ctx.send(f'❌ Error al reproducir: {str(e) or "Error desconocido"}')
            await play_next(ctx)
    else:
        # Opcional: desconectar después de X segundos
        await asyncio.sleep(30)
        if ctx.voice_client and not ctx.voice_client.is_playing():
            await ctx.voice_client.disconnect()
            await ctx.send("⏹️ Si no me hacéis caso po me voy")

@bot.event
async def on_ready():
    print(f'✅ {bot.user} está listo para reproducir música!')

async def search_youtube(query: str, max_results: int = 5):
    """Devuelve una lista de diccionarios con info de los videos."""
    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'ytsearch',
        'extract_flat': True,  # Solo metadata
        'playlistend': max_results
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        # ¡Pasa el query directo! yt-dlp lo convierte en búsqueda automáticamente
        info = ydl.extract_info(f"ytsearch{max_results}:{query}", download=False)
        if 'entries' in info and info['entries']:
            return info['entries']
        return []

@bot.command()
async def play(ctx, *, query: str):
    # Verificación de voz (igual que antes)
    if not ctx.author.voice:
        return await ctx.send("❌ Únete a un canal de voz primero.")
    
    channel = ctx.author.voice.channel
    if not ctx.voice_client:
        await channel.connect()
    elif ctx.voice_client.channel != channel:
        await ctx.voice_client.move_to(channel)

    # Si es URL o playlist → comportamiento normal
    if query.startswith(('http://', 'https://')):
        is_playlist = 'list=' in query
        try:
            if is_playlist:
                await ctx.send("📥 Cargando playlist...")
                loop = asyncio.get_event_loop()
                info = await loop.run_in_executor(None, lambda: ytdl_playlist.extract_info(query, download=False))
                video_urls = [f'https://www.youtube.com/watch?v={e["id"]}' for e in info.get('entries', []) if 'id' in e]
                if not video_urls:
                    return await ctx.send("❌ Playlist vacía o privada.")
                music_queue.add(video_urls)
                await ctx.send(f"✅ Añadidas {len(video_urls)} canciones.")
                if not ctx.voice_client.is_playing():
                    await play_next(ctx)
            else:
                music_queue.add([query])
                if not ctx.voice_client.is_playing():
                    await play_next(ctx)
                else:
                    await ctx.send("✅ Añadido a la cola.")
        except Exception as e:
            await ctx.send(f'❌ Error: {str(e)}')
        return

    # === Es una búsqueda de texto ===
    await ctx.send("🔍 Buscando...")

    results = await search_youtube(query, max_results=5)
    if not results:
        return await ctx.send("❌ No se encontraron resultados.")

    # Guardar resultados para este usuario
    user_selections[ctx.author.id] = results

    # Formatear mensaje con opciones
    msg = "**Elige una canción:**\n"
    for i, video in enumerate(results, 1):
        title = video.get('title', 'Sin título')
        duration = video.get('duration')
        uploader = video.get('uploader', 'Desconocido')
        
        if duration is not None:
            # Asegurarse de que es entero
            duration = int(duration)
            mins, secs = divmod(duration, 60)
            dur_str = f"{mins}:{secs:02d}"
        else:
            dur_str = "??:??"
        
        msg += f"`{i}`. **{title}** ({dur_str}) - *{uploader}*\n"
    
    msg += "\nEscribe el número (1-5) o `cancel`."
    await ctx.send(msg)

    # Esperar respuesta del usuario (solo él)
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel and m.content.lower() in ['1','2','3','4','5','cancel']

    try:
        response = await bot.wait_for('message', check=check, timeout=30.0)
        content = response.content.lower()

        if content == 'cancel':
            user_selections.pop(ctx.author.id, None)
            return await ctx.send("🚫 Búsqueda cancelada.")

        choice = int(content) - 1
        selected = results[choice]
        video_url = f'https://www.youtube.com/watch?v={selected["id"]}'

        # Añadir a la cola
        music_queue.add([video_url])
        if not ctx.voice_client.is_playing():
            await play_next(ctx)
        else:
            await ctx.send(f"✅ **{selected['title']}** añadido a la cola.")

        # Limpiar selección
        user_selections.pop(ctx.author.id, None)

    except asyncio.TimeoutError:
        user_selections.pop(ctx.author.id, None)
        await ctx.send("⏰ Tiempo agotado. Usa `!play` de nuevo.")

@bot.command()
async def stop(ctx):
    music_queue.queue.clear()
    if ctx.voice_client and ctx.voice_client.is_connected():
        await ctx.voice_client.disconnect()
    await ctx.send("⏹️ Chimpón")

@bot.command()
async def skip(ctx):
    if not ctx.voice_client or not ctx.voice_client.is_playing():
        return await ctx.send("❌ No hay nada sonando.")
    ctx.voice_client.stop()  # Esto activa el 'after=' → play_next()
    await ctx.send("⏭️ Siguiente canción...")

@bot.command()
async def queue(ctx):
    if music_queue.is_empty():
        await ctx.send("📭 La cola está vacía.")
    else:
        await ctx.send(f"📜 Hay {len(music_queue.queue)} canción(es) en cola.")

# === Ejecutar el bot ===
bot.run(TOKEN)