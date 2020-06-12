import os
import time
import copy
import torch
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


class BestModelSaveCallback:
    """Save the model with higher accuracy during training.
    
    Arguments:
    ---------
        model_path (string): the file where to save the model.
    """
    
    def __init__(self, model_path):
        self.model_path = model_path
        self.prev_acc = -1.
    # end __init__

    def __call__(self, model, acc):
        """Compare and save the model.
        
        Arguments:
        ---------
            model (torch.nn.Module): the model to be saved.
            acc (float): the accuracy value to be compared.
        """
        if acc >= self.prev_acc:
            print('Saving model...', end=' ')
            best_model = copy.deepcopy(model.state_dict())
            torch.save(best_model, self.model_path)
            self.prev_acc = acc
    # end __call__
# end SaveCallback

def add_bool_arg(parser, name, default=False, **kwargs):
    group = parser.add_mutually_exclusive_group(required=False)
    group.add_argument('--' + name, dest=name.replace('-', '_'), 
                       action='store_true', **kwargs)
    group.add_argument('--no-' + name, dest=name.replace('-', '_'), 
                       action='store_false', **kwargs)
    parser.set_defaults(**{name.replace('-', '_'):default})
# end add_bool_arg

def train_model(model, criterion, optimizer, train_data, val_data, 
                epochs=100, batch_size=32, shuffle_dataset=True, scheduler=None, 
                use_cuda=True, pin_memory=False, callbacks=None):
    # prepare dataset
    train_loader = torch.utils.data.DataLoader(train_data, batch_size=batch_size,
                            pin_memory=pin_memory, shuffle=shuffle_dataset, num_workers=2)
    validation_loader = torch.utils.data.DataLoader(val_data, batch_size=batch_size,
                            pin_memory=pin_memory, shuffle=shuffle_dataset, num_workers=2)

    if use_cuda:
        model.cuda()

    data_loaders = {"train": train_loader, "val": validation_loader}
    data_lengths = {"train": len(train_data), "val": len(val_data)}
    print('Dataset lengths', data_lengths)

    since = time.time()

    best_model_wts = copy.deepcopy(model.state_dict())
    history = dict(
            loss=[], acc=[],
            val_acc=[], val_loss=[]
        )

    for epoch in range(epochs):
        print('Epoch {:03d}/{:03d}'.format(epoch +1, epochs), end=": ")

        # Each epoch has a training and validation phase
        epoch_time = time.time()
        for phase in ['train', 'val']:
            if phase == 'train':
                # optimizer = scheduler(optimizer, epoch)
                model.train()  # Set model to training mode
            else:
                model.eval()  # Set model to evaluate mode

            running_loss = 0.0
            running_acc = 0.0

            # Iterate over data.
            for i, data in enumerate(data_loaders[phase]):
                # get the inputs; data is a list of [inputs, labels]
                inputs, labels = data

                if use_cuda:
                    inputs = inputs.to('cuda')
                    labels = labels.to('cuda')

                # zero the parameter gradients
                optimizer.zero_grad()

                # forward
                outputs = model(inputs)
                loss = criterion(outputs, labels)

                # backward + optimize only if in training phase
                if phase == 'train':
                    loss.backward()
                    # update the weights
                    optimizer.step()

                # statistics
                running_loss += loss.item()
                # Accuracy
                correct = (outputs.argmax(dim=1) == labels).float().sum()
                running_acc += correct

            epoch_loss = running_loss / data_lengths[phase]
            epoch_acc = running_acc / data_lengths[phase]

            loss_key = 'loss' if phase == 'train' else 'val_loss'
            acc_key = 'acc' if phase == 'train' else 'val_acc'
            history[loss_key].append(epoch_loss)
            history[acc_key].append(epoch_acc.item())

            print('{} Loss: {:.4f}'.format(phase.capitalize(), epoch_loss), 
                  'Acc: {:.4f}'.format(epoch_acc), end=" | ")
            # deep copy the model
            if phase == 'val':
                if callbacks is not None:
                    for c in callbacks:
                        c(model, epoch_acc)

        if scheduler is not None:
            scheduler.step()
            for param_group in optimizer.param_groups:
                print('lr: {:.6f}'.format(param_group['lr']))

        epoch_elapsed = time.time() - epoch_time
        print('time elapsed: {:.0f}m {:.0f}s'.format(
        epoch_elapsed // 60, epoch_elapsed % 60))

    time_elapsed = time.time() - since
    print('Training complete in {:.0f}m {:.0f}s'.format(
        time_elapsed // 60, time_elapsed % 60))

    return history, best_model_wts, time_elapsed
# end train_model

def test_model(model, dataset, batch_size=32, use_cuda=True):
    test_loader = torch.utils.data.DataLoader(dataset, batch_size=batch_size,
                                              shuffle=False, num_workers=2)

    print('Evaluating model')
    if use_cuda:
        model.cuda()

    model.eval()  # Set model to evaluate mode

    total = 0
    correct = 0
    Y_test = []
    y_pred = []
    since = time.time()

    with torch.no_grad():
        for data in test_loader:
            images, labels = data

            if use_cuda:
                images = images.to('cuda')
                labels = labels.to('cuda')

            outputs = model(images)

            _, predicted = torch.max(outputs.data, 1)
            total += labels.size(0)
            correct += (predicted == labels).sum().item()
            Y_test.extend(labels.tolist())
            y_pred.extend(torch.nn.functional.softmax(outputs, dim=1).tolist())

    time_elapsed = time.time() - since
    test_accuracy = 100 * correct / total
    print('Completed in {:.0f}m {:.0f}s'.format(
        time_elapsed // 60, time_elapsed % 60))
    print('Accuracy of the network on the test images: {:.2f}%'.format(
            test_accuracy))

    return np.array(Y_test), np.array(y_pred), test_accuracy, time_elapsed

# end test_model

def save_csv(data_source, file_path='history.csv', header=True, index=True):
    if isinstance(data_source, pd.DataFrame):
        data_source.to_csv(file_path, header=header, index=index)
    else:
        df = pd.DataFrame(data=data_source)
        df.to_csv(file_path, header=header, index=index)
    return True
