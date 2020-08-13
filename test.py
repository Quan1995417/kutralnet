import os
import torch
import pickle
import argparse
import numpy as np
from sklearn.metrics import roc_curve, auc
from sklearn.metrics import classification_report
from sklearn.metrics import multilabel_confusion_matrix
from datasets import get_dataset
from datasets import get_preprocessing
from models import get_model
from models import get_model_paths
from models import get_model_params
from models import get_activation
from utils.training import add_bool_arg
from utils.training import test_model
from utils.training import save_csv


def concat_none_class(labels):
    """Expand the distributed representation array with the zero-label."""
    base_labels = np.zeros((labels.shape[0], labels.shape[1] +1))
    base_labels[:, 1:] = labels
    none_idx = np.where(labels.sum(axis=1) == 0)[0]
    base_labels[none_idx, 0] = 1
    return base_labels

parser = argparse.ArgumentParser(description='Fire classification test')
parser.add_argument('--model', metavar='MODEL_ID', default='kutralnet',
                    help='the model ID for training')
parser.add_argument('--model-params', default=None,
                    help='the params to instantiate the model')
parser.add_argument('--activation', default='ce_softmax',
                    help='the activation function for the model')
parser.add_argument('--dataset', metavar='DATASET_ID', default='fismo',
                    help='the dataset ID for training')
parser.add_argument('--dataset-test', metavar='DATASET_TEST_ID', default='firenet_test',
                    help='the dataset ID for test')
parser.add_argument('--dataset-flags', default=None, nargs='*',
                    help='the datasets flags to instaciate the dataset, this \
                        flags can be: \
                            - [no_]one_hot: to one-hot encode or not the labels.\
                            - [no_]distributed: to use or not a distributed representation.\
                            - [no_]multi_label: to allow or not the use of multi-label images.')
parser.add_argument('--version', metavar='VERSION_ID', default=None,
                    help='the training version')
parser.add_argument('--batch-size', default=32, type=int,
                    help='the number of items in the batch')
parser.add_argument('--models-path', default='models',
                    help='the path where storage the models')
add_bool_arg(parser, 'preload-data', default=True, help='choose if load or not the dataset on-memory')
add_bool_arg(parser, 'seed', default=True, help='choose if set or not a seed for random values')
args = parser.parse_args()

# user's selection
model_id = args.model #'kutralnet'
train_dataset_id = args.dataset #'fismo'
test_dataset_id = args.dataset_test #'firenet_test'
version = args.version #None
models_root = args.models_path
# test config
activation_fn = args.activation # 'softmax'
preload_data = bool(args.preload_data) #True # load dataset on-memory
batch_size = args.batch_size #32
must_seed = bool(args.seed)
model_params = args.model_params
dataset_flags = args.dataset_flags
    
# cuda if available
use_cuda = torch.cuda.is_available()
torch_device = 'cpu'

if use_cuda:
    torch_device = 'cuda'

if must_seed:
    # Seed
    seed_val = 666
    torch.manual_seed(seed_val)
    np.random.seed(seed_val)
    
    if use_cuda:
        torch.backends.cudnn.deterministic = True
        torch.backends.cudnn.benchmark = False        

# models parameters
config = get_model_params(model_id)

# common preprocess
transform_params = dict(img_dims=config['img_dims'])
transform_test = get_preprocessing(config['preprocess_test'], transform_params)

# dataset read
data_params = dict(purpose='test', transform=transform_test, preload=preload_data)
data_params.update(dict(dataset_flags=dataset_flags))
test_data = get_dataset(test_dataset_id, params=data_params)

test_num_classes = test_data.num_classes

# model load
model = get_model(model_id, num_classes=test_num_classes, 
                  extra_params=model_params)
# cost function
activation = get_activation(activation_fn)

# read models direclty from the repository's folder
print('Models path:', models_root)
save_path, model_path = get_model_paths(models_root, model_id, 
                                                 train_dataset_id, version)
# load trained model
print('Loading model from {}'.format(model_path))
model.load_state_dict(torch.load(model_path, 
                            map_location=torch.device(torch_device)))
# testing
summary = test_model(model, test_data, activation,
                        batch_size=batch_size, 
                        use_cuda=use_cuda)
# test results
true_labels, y_pred, test_accuracy, test_time = summary

if test_data.one_hot:
    # set 1 to treshold
    treshold = 0.5
    y_pred_class = y_pred.copy()    
    y_pred_class[y_pred_class >= treshold] = 1
    y_pred_class[y_pred_class < treshold] = 0
    
else:    
    # reverse predicted one-hot encoded (network output)
    y_pred_class = np.argmax(y_pred, axis=1)
    
# numbered class    
y_true = true_labels

# label names
label_names = [ label['name'] for key, label in test_data.labels.items() ]

# confussion matrix and metrics
reports = []
matrizes = []
# distributed multi-label have 2 stage test
if test_data.distributed and test_data.multi_label:    
    # add none true class
    multi_y_true = concat_none_class(y_true)    
    # add none pred class
    multi_y_pred_class = concat_none_class(y_pred_class)
    
    print('Distributed multi-label classification report')
    matrizes.append(multilabel_confusion_matrix(multi_y_true, 
                                                multi_y_pred_class))
    print(classification_report(multi_y_true, 
                                multi_y_pred_class, 
                                target_names=label_names))
    
    reports.append(classification_report(multi_y_true, 
                                        multi_y_pred_class, 
                                        target_names=label_names,
                                        output_dict=True))
    
    # emergency detection metrics
    eme_y_true = np.where(true_labels.sum(axis=1) == 0, 0, 1)
    eme_y_pred_class = np.where(y_pred_class.sum(axis=1) == 0, 0, 1)
    
    eme_labels = ['None', 'Emergency']
    print('Fire emergency classification report')
    test_accuracy = (eme_y_true == eme_y_pred_class).mean()
    print('Emergency detection accuracy', test_accuracy)
    matrizes.append(multilabel_confusion_matrix(eme_y_true, 
                                                eme_y_pred_class))
    
    print(classification_report(eme_y_true, 
                                eme_y_pred_class, 
                                target_names=eme_labels))
    reports.append(classification_report(eme_y_true, 
                                        eme_y_pred_class, 
                                        target_names=eme_labels,
                                        output_dict=True))
    
else:
    # printing single only
    print('Classification Report All Labels')
    matrizes.append(multilabel_confusion_matrix(y_true, 
                                                y_pred_class))
    
    print(classification_report(y_true, y_pred_class, target_names=label_names))
    reports.append(classification_report(y_true, 
                                        y_pred_class, 
                                        target_names=label_names,
                                        output_dict=True))

# ROC values and AUROC index
print('Computing area under the ROC curve')
offset = int(test_data.distributed and test_data.multi_label)
roc_data = []

# binary-class
for idx_label in range(len(label_names) -offset):
    
    if test_data.one_hot:# and len(y_true.shape) > 1:
        roc_y_true = y_true[:, idx_label]
    else:
        roc_y_true = np.array(y_true == idx_label, dtype=float)
        
    roc_y_pred = y_pred[:, idx_label]
    
    # Compute ROC curve and ROC area:
    fpr, tpr, _ = roc_curve(roc_y_true, roc_y_pred)
    auroc_val = auc(fpr, tpr)
    
    data = dict(
        label= label_names[idx_label +offset],
        auroc= auroc_val,
        fpr= fpr,
        tpr= tpr,
    )
    roc_data.append(data)
    
    print(data['label'], 'AUROC={:.6f}'.format(data['auroc']))


# save metrics 
with open(os.path.join(save_path,'testing_metrics_{}.pkl'.format(test_dataset_id)),
          'wb') as f:
    pickle.dump(reports, f, pickle.HIGHEST_PROTOCOL)
    pickle.dump(matrizes, f, pickle.HIGHEST_PROTOCOL)
    pickle.dump(roc_data, f, pickle.HIGHEST_PROTOCOL)

# testing summary
test_accuracy /= 100
testing_summary = [
        ('Version', str(version)),
        ('Test dataset', test_data),
        ('Testing time (s)', test_time),
        ('Testing accuracy', test_accuracy),
        ('Using CUDA', use_cuda),
        ('Batch size', batch_size),
    ]

save_csv(testing_summary, 
         file_path=os.path.join(save_path, 
                                'testing_summary_{}.csv'.format(test_dataset_id)),
         header=False,
         index=False)

