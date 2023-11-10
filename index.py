from pytube import Playlist, YouTube


def getSongFileName(videoTitle: str):
    song_name = ""
    for letter in videoTitle:
        if letter.isspace() or letter.isalnum():
            song_name += letter
    return song_name + ".mp3"


def downloadSong(song):
    name = getSongFileName(song.title)
    song.streams.get_audio_only().download("./songs", filename=name)


def downloadOneSong():
    youtubeSongUrl = input("Enter youtube song URL: ")
    youtubeSong = YouTube(youtubeSongUrl)

    try:
        downloadSong(youtubeSong)
    except Exception as e:
        print(f"An error occurred while downloading", youtubeSong.title)


def downloadOnePlaylist():
    youtubePlaylistUrl = input("Enter the youtube playlist URL: ")

    youtubePlaylist = Playlist(youtubePlaylistUrl)

    print("Downloading songs...")

    for video in youtubePlaylist.videos:
        print("", "Starting download of:", video.title)
        try:
            downloadSong(video)
        except Exception as e:
            print(f"An error occurred while downloading", video.title)


def checkResponse(response: str):
    response = response.lower()
    return response == "a" or response == "b"


print("Download youtube script por felipo.")
print("Repository: https://github.com/felipendelicia")
print()

print("You want download:")
print("A - single song")
print("B - complete playlist")

correctAnswer = False
respose = ""

while not correctAnswer:
    response = input("Enter your choise (A/B): ")
    correctAnswer = checkResponse(response)

if response == "a":
    downloadOneSong()
else:
    downloadOnePlaylist()

input("Press any key to exit.")
