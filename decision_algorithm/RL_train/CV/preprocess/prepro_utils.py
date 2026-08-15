try:
    from .models.wavelet.wavelet import wavelet_denoise
except Exception:  # pragma: no cover - optional runtime dependency
    wavelet_denoise = None
try:
    from .models.gamma.gamma import gamma_correction
except Exception:  # pragma: no cover - optional runtime dependency
    gamma_correction = None
try:
    from .models.retinex.retinex import multi_scale_retinex
except Exception:  # pragma: no cover - optional runtime dependency
    multi_scale_retinex = None
try:
    from .models.usm.usm import unsharp_mask
except Exception:  # pragma: no cover - optional runtime dependency
    unsharp_mask = None
try:
    from .models.th_trans.method import th_trans
except Exception:  # pragma: no cover - optional runtime dependency
    th_trans = None
try:
    from .models.RecDerain.test_BRN_real import process
except Exception:  # pragma: no cover - optional runtime dependency
    process = None
try:
    from .models.c2pnet.dehaze import dehaze
except Exception:  # pragma: no cover - optional runtime dependency
    dehaze = None
try:
    from .models.utils.add_foggy import add_foggy
except Exception:  # pragma: no cover - optional runtime dependency
    add_foggy = None
try:
    from .models.utils.add_rainy import add_rainy
except Exception:  # pragma: no cover - optional runtime dependency
    add_rainy = None
try:
    from .models.utils.reverse_preprocessing import add_noise
    from .models.utils.reverse_preprocessing import add_blur
    from .models.utils.reverse_preprocessing import gamma_distort
    from .models.utils.reverse_preprocessing import invert_contrast
    from .models.utils.reverse_preprocessing import remove_edges
except Exception:  # pragma: no cover - optional runtime dependency
    add_noise = None
    add_blur = None
    gamma_distort = None
    invert_contrast = None
    remove_edges = None
import io
from PIL import Image, ImageEnhance, ImageFilter, ImageOps, ImageStat
import subprocess
import random
import torch
import numpy as np
import os
try:
    from torchmetrics.functional import structural_similarity_index_measure as ssim
except Exception:  # pragma: no cover - optional runtime dependency
    ssim = None


def _require_dependency(name, dependency):
    if dependency is None:
        raise RuntimeError(f"Required preprocessing dependency '{name}' is unavailable")
    return dependency


def runtime_estimate_image_quality(image_bytes):
    image = Image.open(io.BytesIO(image_bytes)).convert("L")
    stats = ImageStat.Stat(image)
    min_pixel, max_pixel = stats.extrema[0]
    brightness_mean = float(stats.mean[0])
    contrast_std = float(stats.stddev[0])
    dynamic_range = int(max_pixel - min_pixel)
    low_light = brightness_mean < 72.0
    low_contrast = contrast_std < 28.0 or dynamic_range < 90

    preferred = "none"
    if low_light:
        preferred = "clahe"
    elif low_contrast:
        preferred = "unsharp"

    return {
        "supported": True,
        "brightness_mean": round(brightness_mean, 3),
        "contrast_std": round(contrast_std, 3),
        "dynamic_range": dynamic_range,
        "low_light": low_light,
        "low_contrast": low_contrast,
        "preferred_preprocess": preferred,
    }


def runtime_apply_preprocess(image_bytes, mode):
    if mode == "none":
        return image_bytes

    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

    if mode == "clahe":
        image = ImageOps.equalize(image)
        image = ImageEnhance.Contrast(image).enhance(1.18)
    elif mode == "unsharp":
        if unsharp_mask is not None:
            image_np = np.asarray(image)
            processed = unsharp_mask(image_np)
            image = Image.fromarray(np.asarray(processed).astype(np.uint8))
        else:
            image = image.filter(ImageFilter.UnsharpMask(radius=2, percent=180, threshold=3))
    else:
        raise ValueError(f"unsupported preprocess mode: {mode}")

    buffer = io.BytesIO()
    image.save(buffer, format="JPEG")
    return buffer.getvalue()

# 预处理操作定义
class Gamma:
    def __call__(self, img):
        # 如果输入是tensor，转换为numpy并调整维度
        if isinstance(img, torch.Tensor):
            img = img.permute(1, 2, 0).numpy()  # 从 (C, H, W) 转为 (H, W, C)
        processed_img = _require_dependency("gamma_correction", gamma_correction)(img)
        # 如果处理后是numpy，转换回tensor并调整维度
        if isinstance(processed_img, np.ndarray):
            processed_img = torch.from_numpy(processed_img).permute(2, 0, 1)  # 从 (H, W, C) 转为 (C, H, W)
        return processed_img

class Dehaze:
    def __call__(self, img):
        # 如果输入是tensor，转换为numpy并调整维度
        if isinstance(img, torch.Tensor):
            img = img.permute(1, 2, 0).numpy()  # 从 (C, H, W) 转为 (H, W, C)
        processed_img = _require_dependency("dehaze", dehaze)(img)
        # 如果处理后是numpy，转换回tensor并调整维度
        if isinstance(processed_img, np.ndarray):
            processed_img = torch.from_numpy(processed_img).permute(2, 0, 1)  # 从 (H, W, C) 转为 (C, H, W)
        return processed_img

class Derain:
    def __call__(self, img):
        # 如果输入是tensor，转换为numpy并调整维度
        if isinstance(img, torch.Tensor):
            img = img.permute(1, 2, 0).numpy()  # 从 (C, H, W) 转为 (H, W, C)
        processed_img = _require_dependency("process", process)(img)
        # 如果处理后是numpy，转换回tensor并调整维度
        if isinstance(processed_img, np.ndarray):
            processed_img = torch.from_numpy(processed_img).permute(2, 0, 1)  # 从 (H, W, C) 转为 (C, H, W)
        return processed_img

class Retinex:
    def __call__(self, img):
        # 如果输入是tensor，转换为numpy并调整维度
        if isinstance(img, torch.Tensor):
            img = img.permute(1, 2, 0).numpy()  # 从 (C, H, W) 转为 (H, W, C)
        processed_img = _require_dependency("multi_scale_retinex", multi_scale_retinex)(img)
        # 如果处理后是numpy，转换回tensor并调整维度
        if isinstance(processed_img, np.ndarray):
            processed_img = torch.from_numpy(processed_img).permute(2, 0, 1)  # 从 (H, W, C) 转为 (C, H, W)
        return processed_img

class USM:
    def __call__(self, img):
        # 如果输入是tensor，转换为numpy并调整维度
        if isinstance(img, torch.Tensor):
            img = img.permute(1, 2, 0).numpy()  # 从 (C, H, W) 转为 (H, W, C)
        processed_img = _require_dependency("unsharp_mask", unsharp_mask)(img)
        # 如果处理后是numpy，转换回tensor并调整维度
        if isinstance(processed_img, np.ndarray):
            processed_img = torch.from_numpy(processed_img).permute(2, 0, 1)  # 从 (H, W, C) 转为 (C, H, W)
        return processed_img


class Denoise:
    def __call__(self, img):
        # 如果输入是tensor，转换为numpy并调整维度
        if isinstance(img, torch.Tensor):
            img = img.permute(1, 2, 0).numpy()  # 从 (C, H, W) 转为 (H, W, C)
        processed_img = _require_dependency("wavelet_denoise", wavelet_denoise)(img)
        # 如果处理后是numpy，转换回tensor并调整维度
        if isinstance(processed_img, np.ndarray):
            processed_img = torch.from_numpy(processed_img).permute(2, 0, 1)  # 从 (H, W, C) 转为 (C, H, W)
        return processed_img

class Th_trans:
    def __call__(self, img):
        # 如果输入是tensor，转换为numpy并调整维度
        if isinstance(img, torch.Tensor):
            img = img.permute(1, 2, 0).numpy()  # 从 (C, H, W) 转为 (H, W, C)
        processed_img = _require_dependency("th_trans", th_trans)(img) # 该算法返回一定是灰度图像
        # 如果图像是灰度图像，将其转换为 RGB 图像
        if len(processed_img.shape) == 2:  # 灰度图像的形状是 (H, W)
            # 复制灰度值到 RGB 的三个通道
            processed_img = np.stack((processed_img,) * 3, axis=-1)  # 转换为 (H, W, 3)
        # 如果处理后是numpy，转换回tensor并调整维度
        if isinstance(processed_img, np.ndarray):
            processed_img = torch.from_numpy(processed_img).permute(2, 0, 1)  # 从 (H, W, C) 转为 (C, H, W)
        return processed_img

class Reverse:
    def __init__(self):
        self.methods = [
            method
            for method in [add_foggy, add_rainy, add_noise, add_blur, invert_contrast, remove_edges]
            if method is not None
        ] # gamma_distort

    def __call__(self, img):
        # 如果输入是tensor，转换为numpy并调整维度
        if isinstance(img, torch.Tensor):
            img = img.permute(1, 2, 0).numpy()  # 从 (C, H, W) 转为 (H, W, C)

        # 随机选择一个方法进行处理
        if not self.methods:
            raise RuntimeError("Reverse preprocessing methods are unavailable")
        method = random.choice(self.methods)
        processed_img = method(img)

        # 如果处理后是numpy，转换回tensor并调整维度
        # 如果是灰度图 (H, W)，扩展成 (H, W, 1)
        if isinstance(processed_img, np.ndarray):
            if processed_img.ndim == 2:
                processed_img = np.expand_dims(processed_img, axis=-1)  # (H, W) -> (H, W, 1)
            elif processed_img.ndim == 3 and processed_img.shape[2] == 1:
                pass  # already okay
            elif processed_img.ndim == 3 and processed_img.shape[2] == 3:
                pass  # already RGB
            else:
                raise ValueError(f"Unexpected shape: {processed_img.shape}")

            # 转换回 Tensor，并调整为 (C, H, W)
            processed_img = torch.from_numpy(processed_img).permute(2, 0, 1).float()

        return processed_img

def calculate_ssim_preprocess(x):
    if isinstance(x, np.ndarray):
        x = torch.from_numpy(x).permute(2, 0, 1)  # Convert to CxHxW
    if x.dtype == torch.uint8:
        x = x.float() / 255.0  # Normalize to [0, 1]
    elif x.dtype in [torch.float32, torch.float64]:
        x = x.clamp(0, 1)  # Ensure it's within [0, 1]
    else:
        raise TypeError(f"Unsupported tensor dtype: {x.dtype}")
    if x.dim() == 3:
        x = x.unsqueeze(0)  # Add batch dimension
    return x

def load_image(image_path):
    image = Image.open(image_path).convert('RGB')  # Read image and convert to RGB
    image = np.array(image)  # Convert to NumPy array
    return image


def calculate_ssim(image_path1, image_path2):
    try:
        img1 = load_image(image_path1)  # Load first image
        img2 = load_image(image_path2)  # Load second image

        # Preprocess images to Tensor
        img1_proc = calculate_ssim_preprocess(img1)
        img2_proc = calculate_ssim_preprocess(img2)

        # Compute SSIM using torchmetrics
        ssim_score = _require_dependency("ssim", ssim)(img1_proc, img2_proc)  # data_range=1 for [0, 1] range

        return ssim_score.item()  # Return the SSIM score as a float
    except Exception as e:
        print("Error computing SSIM:", e)
        return -1.0


def preprocessing_use_docker(img_path, output_vis, output_txt, weights_path, model_name):
    folder_path = os.path.dirname(img_path)
    image_file = os.path.basename(img_path)
    weight_name = ""
    if "derain" in model_name:
        weight_name = 'Derain.pth'
    elif "dehaze" in model_name:
        weight_name = 'Dehaze.pkl'
    else:
        # 传统算法不需要权重，这里设置一个假值即可
        weight_name = "dummy.pth"
    password = os.getenv("SUDO_PASSWORD", "")
    if not password:
        raise RuntimeError("SUDO_PASSWORD environment variable is required")
    command = [
        'sudo', '-S', 'docker', 'run', '--gpus', 'all', '--rm',
        '--user', f'{os.getuid()}:{os.getgid()}',
        '-v', f'{folder_path}:/preprocessing/input',
        '-v', f'{output_vis}:/preprocessing/output_vis',
        '-v', f'{output_txt}:/preprocessing/output_txt',
        '-v', f'{weights_path}:/preprocessing/model',
        'preprocessing:v1',
        'python', 'preprocessing.py', '--model_name', f'{model_name}', '--input', f'/preprocessing/input/{image_file}',
        '--output_vis', '/preprocessing/output_vis', '--output_txt', '/preprocessing/output_txt',
        '--model', f'/preprocessing/model/{weight_name}'
    ]
    subprocess.run(command, input=f'{password}\n'.encode())
    # 获取图像文件名和基名（不带扩展名）
    img_name = os.path.basename(img_path)
    img_basename = os.path.splitext(img_name)[0]
    result_txt_path = os.path.join(output_txt, f"{img_basename}.txt")
    # 查找并读取对应的txt结果文件
    if os.path.exists(result_txt_path):
        with open(result_txt_path, 'a') as f:
            f.write(f"path: {img_path}\n")
    else:
        raise FileNotFoundError(f"Result file not found: {result_txt_path}")
    image_path1 = os.path.join(output_vis, image_file)
    image_path2 = img_path.replace("reverse", "origin")

    ssim_score = calculate_ssim(image_path1, image_path2)
    return ssim_score
