from pytube import Playlist

print("Download youtube script por felipo.")
print("Repository: https://github.com/felipendelicia")
print()

youtubePlaylistUrl = input("Enter the youtube playlist URL: ")

youtubePlaylist = Playlist(youtubePlaylistUrl)

print("Downloading songs...")

for video in youtubePlaylist.videos:
    print("", "Starting download of:", video.title)
    song_name = video.title + ".mp3"
    video.streams.get_audio_only().download(filename=song_name)

input("Press any key to exit.")