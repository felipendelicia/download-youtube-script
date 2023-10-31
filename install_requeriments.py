import subprocess
import os

path = os.getcwd()

response = subprocess.run("pip install -r requeriments.txt", shell=True, capture_output=True, text=True)

print("Console output:")
print(response.stdout)

input("Press any key to exit.")