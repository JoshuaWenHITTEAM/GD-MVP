import random
import gym
import torch
import numpy as np
import torchvision.transforms as transforms
from torch.utils.data import DataLoader
from gym import spaces
from collections import namedtuple
import torch.nn.functional as F
from torchvision import datasets
from .prepro_utils import *
from torchvision.datasets import ImageFolder
from torchmetrics.functional import structural_similarity_index_measure as ssim
import torch.nn.functional as F
import os


PREPROCESSING_ACTIONS = {
    "none": transforms.Lambda(lambda x: x),
    "denoise": Denoise(),
    "derain": Derain(),
    "dehaze": Dehaze(),
    "gamma": Gamma(),
    "retinex": Retinex(),
    "usm": USM(),
    "th_trans": Th_trans()
}

reverse = Reverse()


class ImagePreprocessingEnv(gym.Env):
    def __init__(self, dataset_path, device='cuda'):
        super(ImagePreprocessingEnv, self).__init__()
        self.actions = list(PREPROCESSING_ACTIONS.keys())
        self.num_actions = len(self.actions)
        self.action_space = spaces.Discrete(self.num_actions)
        self.action_name = ''

        self.n_channels = 3
        self.frame_width = 256
        self.frame_height = 256
        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(self.n_channels, self.frame_width, self.frame_height), dtype=np.float32
        )

        # 读取数据集
        self.test_loaders = self.load_datasets(dataset_path)
        self.current_loader = None
        self.current_iter = None
        self.observation = None
        self.original_image = None  # 记录原始图像
        self.reverse_image = None  # 记录原始图像



    def load_datasets(self, dataset_path):
        test_loaders = {}

        # 在这里定义一个transform，以确保加载时图像被转换成Tensor类型
        transform = transforms.Compose([
            transforms.ToTensor()
        ])

        for modality in ['SAR', 'RGB', 'IR']:
            val_path = os.path.join(dataset_path, modality, 'val')
            dataset = ImageFolder(root=val_path, transform=transform)
            test_loaders[modality] = DataLoader(dataset, batch_size=1, shuffle=True)

        return test_loaders

    def reset(self):
        modality = random.choice(list(self.test_loaders.keys()))
        self.current_loader = iter(self.test_loaders[modality])
        return self.get_next_state()

    def get_next_state(self):
        try:
            data, _ = next(self.current_loader)
        except StopIteration:
            self.current_loader = iter(self.test_loaders[random.choice(list(self.test_loaders.keys()))])
            data, _ = next(self.current_loader)

        transform = transforms.Compose([
            transforms.Resize((256, 256)),
            transforms.Normalize(mean=[0.5], std=[0.5])
        ])
        data = transform(data[0])  # data[0]是单个图像!
        self.original_image = data
        # add noise here
        processed_reverse_data = reverse(data)  # 对 img 随机应用一种反面处理方法
        self.observation = processed_reverse_data
        return processed_reverse_data


    def step(self, action):
        action_name = self.actions[action]
        self.action_name = action_name
        try:
            transform = PREPROCESSING_ACTIONS[action_name]
            processed_img = transform(self.observation.squeeze(0)).unsqueeze(0)
            reward = self.evaluate(processed_img)
        except:
            # 若因图像通道不匹配等问题报错，则直接返回惩罚值
            reward = -1
        next_state = self.get_next_state()
        done = False
        info = {
            "episode": {
                "a": action,
                "r": reward,
                "l": 0,
                "n": 0
            },
        }

        return next_state, reward, done, info

    # def evaluate(self, img):
    #     try:
    #         mse = F.mse_loss(img, self.original_image).item()  # 计算均方误差
    #     except:
    #         print(img)
    #         print(self.original_image)
    #     reward = 1 / (1 + mse)  # 归一化到 0-1
    #     return reward

    def evaluate(self, img):
        try:
            # 保证 img 和 self.original_image 是 float 类型，范围 [0, 1]
            def preprocess(x):
                if x.dtype == torch.uint8:
                    x = x.float() / 255.0
                elif x.dtype in [torch.float32, torch.float64]:
                    x = x.clamp(0, 1)  # 保证范围在 [0, 1]
                else:
                    raise TypeError(f"Unsupported tensor dtype: {x.dtype}")
                # 如果缺少 batch 维度，则加上
                if x.dim() == 3:
                    x = x.unsqueeze(0)
                return x

            img_proc = preprocess(img)
            orig_proc = preprocess(self.original_image)
            # 计算 SSIM
            ssim_score = ssim(img_proc, orig_proc)
            reward = ssim_score.item()
            if np.isnan(reward):
                reward = -1.0
        except Exception as e:
            print("Error computing SSIM:", e)
            print("img dtype:", img.dtype, "shape:", img.shape)
            print("original dtype:", self.original_image.dtype, "shape:", self.original_image.shape)
            reward = 0.0

        return reward

    def render(self):
        pass

    def close(self):
        pass
