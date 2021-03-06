import numpy as np
import re
import functools


class AverageMeter(object):
    """Computes and stores the average and current value"""
    def __init__(self):
        self.initialized = False
        self.val = None
        self.avg = None
        self.sum = None
        self.count = None

    def initialize(self, val, weight):
        self.val = val
        self.avg = val
        self.sum = val * weight
        self.count = weight
        self.initialized = True

    def update(self, val, weight=1):
        if not self.initialized:
            self.initialize(val, weight)
        else:
            self.add(val, weight)

    def add(self, val, weight):
        self.val = val
        self.sum += val * weight
        self.count += weight
        self.avg = self.sum / self.count

    def value(self):
        return self.val

    def average(self):
        return self.avg


def accuracy(preds, label):
    """Computes prediction accuracy"""
    valid = (label >= 0)
    acc_sum = (valid * (preds.int() == label.int())).sum()
    valid_sum = valid.sum()
    acc = float(acc_sum) / float(valid_sum + 1e-10)
    return acc


def intersectionAndUnion(imPred, imLab, numClass):
    imPred = np.asarray(imPred.int().cpu().detach().numpy()).copy()
    imLab = np.asarray(imLab.int().cpu().detach().numpy()).copy()

    imPred += 1
    imLab += 1
    # Remove classes from unlabeled pixels in gt images.
    # We should not penalize detections in unlabeled portions of the images.
    imPred = imPred * (imLab > 0)

    # Compute area intersection:
    intersection = imPred * (imPred == imLab)
    (area_intersection, _) = np.histogram(intersection, bins=numClass, range=(1, numClass))

    # Compute area union:
    (area_pred, _) = np.histogram(imPred, bins=numClass, range=(1, numClass))
    (area_lab, _) = np.histogram(imLab, bins=numClass, range=(1, numClass))
    area_union = area_pred + area_lab - area_intersection

    return (area_intersection, area_union)


