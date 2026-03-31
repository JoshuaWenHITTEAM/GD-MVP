import cv2
import numpy as np
import pywt


def gamma_correction(image_rgb: np.ndarray, gamma: float = 1.5) -> np.ndarray:
    table = np.array([(i / 255.0) ** gamma * 255 for i in range(256)], dtype=np.uint8)
    return cv2.LUT(image_rgb.astype(np.uint8), table)


def single_scale_retinex(img: np.ndarray, sigma: float) -> np.ndarray:
    blur = cv2.GaussianBlur(img, (0, 0), sigma)
    return np.log1p(img) - np.log1p(blur + 1e-6)


def multi_scale_retinex(image_rgb: np.ndarray, sigmas=None) -> np.ndarray:
    if sigmas is None:
        sigmas = [15, 80, 250]
    img = image_rgb.astype(np.float32) + 1.0
    retinex = sum(single_scale_retinex(img, sigma) for sigma in sigmas) / len(sigmas)
    return cv2.normalize(retinex, None, 0, 255, cv2.NORM_MINMAX).astype(np.uint8)


def unsharp_mask(image_rgb: np.ndarray, sigma: float = 1.0, strength: float = 1.5) -> np.ndarray:
    blurred = cv2.GaussianBlur(image_rgb, (0, 0), sigma)
    return cv2.addWeighted(image_rgb, 1 + strength, blurred, -strength, 0)


def wavelet_denoise(image_rgb: np.ndarray, wavelet: str = "db1", level: int = 1, threshold_factor: float = 3) -> np.ndarray:
    denoised_image = np.zeros_like(image_rgb)

    for i in range(3):
        channel = image_rgb[:, :, i]
        coeffs = pywt.wavedec2(channel, wavelet, level=level)
        cA, details = coeffs[0], coeffs[1:]
        cH, cV, cD = details[0]
        sigma = np.median(np.abs(cH)) / 0.6745 if np.any(cH) else 0
        threshold = threshold_factor * sigma
        filtered_details = []
        for detail_h, detail_v, detail_d in details:
            filtered_details.append(
                (
                    pywt.threshold(detail_h, threshold, mode="soft"),
                    pywt.threshold(detail_v, threshold, mode="soft"),
                    pywt.threshold(detail_d, threshold, mode="soft"),
                )
            )
        denoised_channel = pywt.waverec2([cA, *filtered_details], wavelet)
        denoised_image[:, :, i] = denoised_channel[: image_rgb.shape[0], : image_rgb.shape[1]]

    return np.clip(denoised_image, 0, 255).astype(np.uint8)

