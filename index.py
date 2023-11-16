from pytube import Playlist, YouTube

def getSongFileName(videoTitle: str)->str:
    song_name = ""
    for letter in videoTitle:
        if letter.isspace() or letter.isalnum():
            song_name += letter
    return song_name + ".mp3"

def downloadSong(url:str):
    song = YouTube(url)
    name = getSongFileName(song.title)
    print("", "Starting download of:", song.title)
    try:
        song.streams.get_audio_only().download("./songs", filename=name)
    except:
        print(f"Error downloading this song: {name}")
    
def downloadPlaylist(url:str):
    playlist = Playlist(url)

    for video in playlist.videos:
        downloadSong(video.watch_url)

def checkResponse(response: str):
    response = response.lower()
    return response == "a" or response == "b"

def initPrintText():
    print("Download youtube script by felipendelicia.")
    print("Repository: https://github.com/felipendelicia/download-youtube-script")
    print()

    print("You want download:")
    print("A - single song")
    print("B - complete playlist")

    answer = False
    response = ""

    while not answer:
        response = input("Enter your choise (A/B): ")
        answer = checkResponse(response)

    return response.lower()

def isPlaylist(url:str)->bool:
    return "playlist" in url

def main():
    initPrintText()
    youtubeURL = input("Enter the playlist/song URL: ")

    print("Starting download...")

    if isPlaylist(youtubeURL):
        downloadPlaylist(youtubeURL)
    else:
        downloadSong(youtubeURL)

    input("Press any key to exit...")
    

if __name__ == "__main__":
    main()
