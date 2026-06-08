# prepare_installer_logos.py
from PIL import Image

# Large side banner (164 x 314 pixels)
img = Image.open("logo.png").convert("RGB")
img_large = img.resize((164, 314), Image.LANCZOS)
img_large.save("logo_installer.bmp", format="BMP")

# Small top-right image (55 x 55 pixels)
img_small = img.resize((55, 55), Image.LANCZOS)
img_small.save("logo_small.bmp", format="BMP")

print("BMP logos created!")