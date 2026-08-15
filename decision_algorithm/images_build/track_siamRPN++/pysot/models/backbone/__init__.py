# Copyright (c) SenseTime. All Rights Reserved.

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from pysot.models.backbone.resnet_atrous import resnet50

BACKBONES = {
    'resnet50': resnet50,
}


def get_backbone(name, **kwargs):
    return BACKBONES[name](**kwargs)
