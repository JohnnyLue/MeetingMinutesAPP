import cv2
import numpy as np
from PIL import ImageFont, ImageDraw, Image
import wave
import winsound

def PutText(img, text, x_y, fontColor = (0, 255, 0), fontScale = 30, anchor = 'lt'):
    img = Image.fromarray(img)
    draw = ImageDraw.Draw(img)
    fontText = ImageFont.truetype("font/mingliu.ttc", fontScale, encoding="utf-8")
    draw.text((x_y), text, fontColor, font=fontText, anchor=anchor, stroke_fill=(0, 0, 0), stroke_width=1)
    frame = np.array(img)
    return frame

class WavPlayer:
    def __init__(self, path):
        self.path = path
    
    def play(self):
        wf = wave.open(self.path, 'rb')
        winsound.PlaySound(None, winsound.SND_ASYNC|winsound.SND_NOSTOP)