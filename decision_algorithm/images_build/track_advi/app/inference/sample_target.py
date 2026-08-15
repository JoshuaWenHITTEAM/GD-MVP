import math

import cv2 as cv
import numpy as np


def sample_target(im, target_bb, search_area_factor, output_sz=None):
    """Extract a square search/template crop around the target box."""
    if not isinstance(target_bb, list):
        x, y, w, h = target_bb.tolist()
    else:
        x, y, w, h = target_bb

    crop_sz = math.ceil(math.sqrt(w * h) * search_area_factor)
    if crop_sz < 1:
        raise ValueError("too small bounding box")

    x1 = round(x + 0.5 * w - crop_sz * 0.5)
    x2 = x1 + crop_sz
    y1 = round(y + 0.5 * h - crop_sz * 0.5)
    y2 = y1 + crop_sz

    x1_pad = max(0, -x1)
    x2_pad = max(x2 - im.shape[1] + 1, 0)
    y1_pad = max(0, -y1)
    y2_pad = max(y2 - im.shape[0] + 1, 0)

    if im.ndim == 2:
        im_crop = im[y1 + y1_pad : y2 - y2_pad, x1 + x1_pad : x2 - x2_pad]
    else:
        im_crop = im[y1 + y1_pad : y2 - y2_pad, x1 + x1_pad : x2 - x2_pad, :]
    im_crop_padded = cv.copyMakeBorder(im_crop, y1_pad, y2_pad, x1_pad, x2_pad, cv.BORDER_CONSTANT)

    height, width = im_crop_padded.shape[:2]
    att_mask = np.ones((height, width))
    end_x, end_y = -x2_pad, -y2_pad
    if y2_pad == 0:
        end_y = None
    if x2_pad == 0:
        end_x = None
    att_mask[y1_pad:end_y, x1_pad:end_x] = 0

    if output_sz is None:
        return im_crop_padded, att_mask.astype(np.bool_), 1.0

    resize_factor = output_sz / crop_sz
    im_crop_padded = cv.resize(im_crop_padded, (output_sz, output_sz))
    att_mask = cv.resize(att_mask, (output_sz, output_sz)).astype(np.bool_)
    return im_crop_padded, resize_factor, att_mask
