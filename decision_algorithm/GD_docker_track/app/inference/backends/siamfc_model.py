import torch
import torch.nn as nn
import torch.nn.functional as F


class SiamFCBackbone(nn.Module):
    def __init__(self):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(3, 96, kernel_size=11, stride=2),
            nn.BatchNorm2d(96),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=3, stride=2),
            nn.Conv2d(96, 256, kernel_size=5, groups=2),
            nn.BatchNorm2d(256),
            nn.ReLU(inplace=True),
            nn.MaxPool2d(kernel_size=3, stride=2),
            nn.Conv2d(256, 384, kernel_size=3),
            nn.BatchNorm2d(384),
            nn.ReLU(inplace=True),
            nn.Conv2d(384, 384, kernel_size=3, groups=2),
            nn.BatchNorm2d(384),
            nn.ReLU(inplace=True),
            nn.Conv2d(384, 256, kernel_size=3, groups=2),
        )

    def forward(self, x):
        return self.features(x)


class SiamFCNet(nn.Module):
    def __init__(self, out_scale: float = 0.001):
        super().__init__()
        self.backbone = SiamFCBackbone()
        self.out_scale = out_scale
        self.total_stride = 8

    def feature(self, x):
        return self.backbone(x)

    def correlate(self, exemplar_feat, search_feat):
        response = F.conv2d(search_feat, exemplar_feat)
        return response * self.out_scale

