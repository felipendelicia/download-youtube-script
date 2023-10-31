from pytube import Playlist

def getSongFileName(videoTitle:str):
    song_name = "";
    for letter in videoTitle:
        if letter.isspace() or letter.isalnum():
            song_name += letter
    return song_name + ".mp3"


print("Download youtube script por felipo.")
print("Repository: https://github.com/felipendelicia")
print()

youtubePlaylistUrl = input("Enter the youtube playlist URL: ")

youtubePlaylist = Playlist(youtubePlaylistUrl)

print("Downloading songs...")

for video in youtubePlaylist.videos:
    print("", "Starting download of:", video.title)
    song_name = getSongFileName(video.title)
    try:
        video.streams.get_audio_only().download("./songs",filename=song_name)
    except Exception as e:
        print(f"An error occurred while downloading {song_name}: {e}")

input("Press any key to exit.")