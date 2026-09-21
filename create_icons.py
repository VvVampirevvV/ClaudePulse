from PIL import Image, ImageDraw
import os

os.makedirs("assets", exist_ok=True)

def create_icon(filename, color):
    img = Image.new('RGBA', (64, 64), color=(0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((4, 4, 60, 60), fill=color, outline="white", width=3)
    img.save(os.path.join("assets", filename))

create_icon("icon.ico", (41, 128, 185)) # Blue
create_icon("icon_active.ico", (39, 174, 96)) # Green

print("Icons created in assets folder.")
