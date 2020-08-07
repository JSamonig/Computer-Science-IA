import cv2
import numpy as np

filename = "./uploads/images/" + "tesco-shopping.jpg"  # "sample_receipt.jpg"

image = cv2.imread(filename, 0)


def scaleUp(image):
    return cv2.resize(image, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)


def contrastIncrease(image):
    alpha = 1  # Contrast control (1.0-3.0)
    beta = 35  # Brightness control (0-100)

    return cv2.convertScaleAbs(image, alpha=alpha, beta=beta)


def binarize(image):
    return cv2.adaptiveThreshold(image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 2)


def removeNoise(image):
    return cv2.GaussianBlur(image, (5, 5), 0)


def deskew(image):
    coords = np.column_stack(np.where(image > 0))
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = -(90 + angle)

    else:
        angle = -angle
    (h, w) = image.shape[:2]
    center = (w // 2, h // 2)
    M = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(image, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return rotated

def main(image):
    adjusted = contrastIncrease(scaleUp(image))
    return image#adjusted

'''
cv2.imshow("Image", adjusted)

# waiting for key event
cv2.waitKey(0)

# destroying all windows
cv2.destroyAllWindows()
'''