import torch
import torch.nn as nn
import numpy as np
# from tensorboardX import SummaryWriter

from dataloader import get_data_loader
from evaluate import evaluate
import torch.optim as optim
import time, os
from PIL import Image
from fcn32s import FCN32s
from fcn16s import FCN16s
from fcn8s import FCN8s
from evaluate import cross_entropy2d


class Trainer(object):
    def __init__(self, args):
        super(Trainer, self).__init__()
        self.epoch = args.epoch
        self.batch_size = args.batch_size
        self.data_dir = args.data_dir

        self.save_dir = args.save_dir
        self.result_dir = args.result_dir
        self.log_dir = args.log_dir
        self.gpu_mode = args.gpu_mode
        self.verbose = args.verbose

        if args.model == 'fcn16s':
            self.model = FCN16s()
        elif args.model == 'fcn32s':
            self.model = FCN32s()
        elif args.model == 'fcn8s':
            self.model = FCN8s()
        else:
            print("No this model type")
            exit(-1)
        if self.gpu_mode:
            self.model = self.model.cuda()
        self.parameter = self.model.parameters()
        self.optimizer = optim.Adam(self.parameter, lr=args.learning_rate)
        self.scheduler = optim.lr_scheduler.ExponentialLR(self.optimizer, gamma=0.5)

        self.train_dataloader = get_data_loader(self.data_dir, self.batch_size, split='train')
        self.test_dataloader = get_data_loader(self.data_dir, 1, split='val')

        # experiment_id = args.model + time.strftime('%m%d%H%m')
        # self.writer = SummaryWriter(log_dir=self.log_dir + '/tboard_' + experiment_id)

        if args.pretrain != '':
            self._load_pretrain(args.pretrain)

    def train(self):
        self.train_hist = {
            'loss': [],
            'per_epoch_time': [],
            'total_time': []
        }

        print('training start!!')
        start_time = time.time()

        self.model.train()
        best_iou = -1
        for epoch in range(self.epoch):
            self.train_epoch(epoch, self.verbose)

            if (epoch + 1) % 1 == 0 or epoch == 0:
                res = self.evaluate()
                print('Evaluation: Epoch %d: Iou_mean: %.4f, Acc: %.4f, Loss: %.4f,  ' % (
                    epoch + 1, res['iou_mean'], res['acc'], res['loss']))
                print("IOU:", list(res['iou']))
                if res['iou_mean'] > best_iou:
                    best_iou = res['iou_mean']
                    self._save_model('best')

            if epoch % 10 == 0:
                self.scheduler.step()

            if (epoch + 1) % 5 == 0:
                self._save_model(epoch + 1)

            # if self.writer:
            #     self.writer.add_scalar('Learning Rate', self._get_lr(), epoch)
            #     self.writer.add_scalar('Loss', res['loss'], epoch)

        # finish all epoch
        self.train_hist['total_time'].append(time.time() - start_time)
        print("Avg one epoch time: %.2f, total %d epochs time: %.2f" % (np.mean(self.train_hist['per_epoch_time']),
                                                                        self.epoch, self.train_hist['total_time'][0]))
        print("Training finish!... save training results")

    def train_epoch(self, epoch, verbose=False):
        epoch_start_time = time.time()
        loss_buf = []
        num_batch = int(len(self.train_dataloader.dataset) / self.batch_size)
        for iter, (img, msk, _) in enumerate(self.train_dataloader):
            if self.gpu_mode:
                img = img.cuda()
                msk = msk.cuda()
            # forward
            self.optimizer.zero_grad()
            output = self.model(img)
            loss = cross_entropy2d(output, msk)
            # backward
            loss.backward()
            self.optimizer.step()
            loss_buf.append(loss.detach().cpu().numpy())
            if (iter + 1) % 100 == 0 and verbose:
                print("Epoch %d [%4d/%d] loss: %.4f, time: %.4f" % (
                    epoch + 1, iter + 1, num_batch + 1, loss, time.time() - epoch_start_time))
        # finish one epoch
        epoch_time = time.time() - epoch_start_time
        self.train_hist['per_epoch_time'].append(epoch_time)
        self.train_hist['loss'].append(np.mean(loss_buf))
        print('Epoch %d: Loss: %.4f, time %.4f s' % (epoch + 1, np.mean(loss_buf), epoch_time))
        # print(f'Epoch {epoch+1}: Loss {np.mean(loss_buf)}, time {epoch_time:.4f}s')

    def evaluate(self):
        self.model.eval()
        res = evaluate(self.model, self.test_dataloader, self.gpu_mode)
        self.model.train()
        return res

    def _save_model(self, epoch):
        save_path = self.save_dir + "/model_" + str(epoch) + '.pkl'
        torch.save(self.model.state_dict(), save_path)
        print("Save model to %s" % save_path)

    def _load_pretrain(self, pretrain):
        state_dict = torch.load(pretrain, map_location='cpu')
        self.model.load_state_dict(state_dict)
        print("Load model from %s" % pretrain)

    def _get_lr(self, group=0):
        return self.optimizer.param_groups[group]['lr']

    def generate_output(self):
        save_dir = os.path.join(self.data_dir, 'val/predicts/')
        for iter, (img, msk, id) in enumerate(self.test_dataloader):
            id = id[0]
            if self.gpu_mode:
                img = img.cuda()
                msk = msk.cuda()
            output = self.model(img).max(1)[1]
            output = output.numpy()[0]
            im = Image.fromarray(np.uint8(output))
            im.save(save_dir + id + '.png')
            # Image.save(save_dir + id + '.png', output)
            print("save %s.png" % save_dir)
