# -*- coding: utf-8 -*-
import os
import sys
import cv2
import math
import glob
import numpy as np
import pandas as pd

# constant
fire_label = 'fire'
no_fire_label = 'no_fire'

# data preprocess
def clean_string(string):
    return string.rstrip().replace('./', '')
# end clean_string

#from video to dataset
def get_frames_from_video(video_path, prev_imgs=None, debug=False):
    imgs = [] if prev_imgs is None else prev_imgs

    cap_qt = 0
    frame_count = 0 #numbers of frame
    cap = cv2.VideoCapture(video_path)
    mog = cv2.createBackgroundSubtractorMOG2()

    width = int(cap.get(3))
    height = int(cap.get(4))

    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)

    #get one frame per second
    frames_skip = int(fps)
    frames_qt = int(total_frames / fps)

    print('Video Info:',
        '{}x{}'.format(width, height),
        'FPS: {:.3f}'.format(fps),
        'Total Frames: {}'.format(total_frames),
        'skips: {}'.format(frames_skip),
        'qt: {}'.format(frames_qt))

    while True:
        if cap_qt == frames_qt:
            break

        frame_count += 1 # frames add

        if (frame_count%frames_skip) == 0:
            #print("filename:{}, cnt:{}".format(video_path, cap_qt+1))
            ret, frame = cap.read()
            if ret == False:
                break
            imgs.append(frame)
            cap_qt += 1

    cap.release()

    return imgs
# end get_dataset_from_video

def extract_frames_to_folder(videos_path, prefix, save_folder):
    videos = glob.glob(os.path.join(videos_path, '*.avi'))
    #frame storage
    imgs = []

    print('Loading video frames with 1 FPS interval...')

    print(len(videos), 'videos found at', videos_path)
    for video_path in videos:
        fire_imgs = get_frames_from_video(video_path,
                                            prev_imgs=imgs)

    if not os.path.exists(save_folder):
        os.makedirs(save_folder)

    i = 0
    for image in imgs:
        filename = '{}{:05d}.png'.format(prefix, i)
        cv2.imwrite(os.path.join(save_folder, filename),image)
        i += 1

    print('Done')
# end extract_frames_to_folder

def save_dataframe(dataframe, folder_path, filename='dataset.csv'):
    csv_path = os.path.join(folder_path, filename)
    dataframe.to_csv(csv_path, index=False)
    print('Saved at', csv_path)
# end save_dataframe

def split_dataframe(dataframe, quantity):
    # shufle data and reset
    dataframe = dataframe.sample(frac=1.)
    dataframe.reset_index(drop=True, inplace=True)

    # purpose labeling
    dataframe['purpose'] = 'train'
    dataframe.loc[dataframe.tail(quantity).index, 'purpose'] = 'test'

    return dataframe
# end split_dataframe

# FiSmo Dataset
def prepare_fire_smoke_df(fismo_path):
    # FlickrFireSmoke
    folder_name = 'Flickr-FireSmoke'
    flickr_fire_smoke_dt = os.path.join(fismo_path, folder_name)

    # load classes from csv
    csv_path = os.path.join(flickr_fire_smoke_dt, 'imagenames-classes.csv')
    fire_smoke_df = pd.read_csv(csv_path,
                            header=None,
                            names=['image_id', 'have_fire', 'have_smoke'])
    # removes duplicates
    fire_smoke_df.drop_duplicates(subset='image_id', inplace=True)

    # add class column
    classes = []
    for have_fire in fire_smoke_df['have_fire']:
        if bool(have_fire):
            classes.append(fire_label)
        else:
            classes.append(no_fire_label)
    fire_smoke_df['class'] = classes

    # removes extra classification columns
    del fire_smoke_df['have_fire']
    del fire_smoke_df['have_smoke']

    # add folder path
    folder_path = os.path.join(folder_name, 'imgs')
    fire_smoke_df.insert(0, 'folder_path', folder_path)

    return fire_smoke_df
# end prepare_fire_smoke_df

def prepare_flickr_fire_df(fismo_path):
    # FlickFire
    folder_name = 'Flickr-Fire'
    flickr_fire_dt = os.path.join(fismo_path, folder_name)

    # load fire ids from txt
    txt_path = os.path.join(flickr_fire_dt, 'flamesId.txt')
    tmp_df = pd.read_csv(txt_path,
                        header=None,
                        names=['image_id'])

    # add class column
    tmp_df['class'] = fire_label

    # add folder path
    folder_path = os.path.join(folder_name, 'Flickr-Fire_flame')
    tmp_df.insert(0, 'folder_path', folder_path)

    # tmp allocation
    fire_df = tmp_df

    # load fire ids from txt
    txt_path = os.path.join(flickr_fire_dt, 'notFlamesId.txt')
    tmp_df = pd.read_csv(txt_path,
                        header=None,
                        names=['image_id'])

    # add class column
    tmp_df['class'] = no_fire_label

    # add folder path
    # path must be confirmed
    folder_path = os.path.join(folder_name, 'Flickr-Fire_flame')
    tmp_df.insert(0, 'folder_path', folder_path)

    # dataset's  dataframe
    flickr_fire_df = pd.concat([fire_df, tmp_df])

    # removes duplicates
    flickr_fire_df.drop_duplicates(subset='image_id', inplace=True)

    return flickr_fire_df
# end prepare_flickr_fire_df

def prepare_bowfire_df(fismo_path):
    # BoWFire
    folder_name = 'BoWFire'
    bowfire_dt = os.path.join(fismo_path, folder_name)

    # load only test dataset
    csv_path = os.path.join(bowfire_dt, 'dataset.csv')
    bowfire_df = pd.read_csv(csv_path, header=None,
                             names=['image_path', 'ground_truth'],
                             skiprows=1)

    # removes extra info and clean string
    bowfire_df['image_path'] = bowfire_df['image_path'].apply(clean_string)
    del bowfire_df['ground_truth']

    # transform for image path to folder_path, image_id and class
    folder_paths = []
    image_ids = []
    classes = []
    for image_path in bowfire_df['image_path']:
        # separate path name
        splitted = image_path.split(os.path.sep)
        image_id = splitted[-1]
        splitted.pop()
        folder_path = os.path.join(folder_name, os.path.sep.join(splitted))
        # append
        folder_paths.append(folder_path)
        image_ids.append(image_id)
        if 'not_fire' in image_id:
            classes.append(no_fire_label)
        else:
            classes.append(fire_label)

    # add columns
    bowfire_df['folder_path'] = folder_paths
    bowfire_df['image_id'] = image_ids
    bowfire_df['class'] = classes

    # remove column
    del bowfire_df['image_path']

    return bowfire_df
# end prepare_bowfire_df

def prepare_fismo_df(fismo_path):
    print('Starting FiSmo dataset preparation....')
    # FlickrFireSmoke
    print('Preparing FlickrFireSmoke...')
    fire_smoke_df = prepare_fire_smoke_df(fismo_path)

    # FlickFire
    print('Preparing FlickrFire...')
    flickr_fire_df = prepare_flickr_fire_df(fismo_path)

    # BoWFire
    print('Preparing BoWFire...')
    bowfire_df = prepare_bowfire_df(fismo_path)

    # FiSmo merge
    fismo_df = pd.concat([fire_smoke_df, flickr_fire_df, bowfire_df])
    # removes duplicates
    fismo_df.drop_duplicates(subset='image_id', inplace=True)

    # classes count
    classes_qt = fismo_df['class'].value_counts()

    print('Splitting dataset...')
    # fire dataset validation split
    test_size = .2
    test_qt = math.ceil(classes_qt[fire_label] * test_size)

    # class separation
    fire_df = fismo_df.loc[fismo_df['class'] == fire_label]
    fire_df = split_dataframe(fire_df, test_qt)

    # no fire dataset validation split
    test_qt = math.ceil(classes_qt[no_fire_label] * test_size)

    # class separation
    no_fire_df = fismo_df.loc[fismo_df['class'] == no_fire_label]
    no_fire_df = split_dataframe(no_fire_df, test_qt)

    # concat splitted dataset
    fismo_df = pd.concat([fire_df, no_fire_df])

    # order data reset
    fismo_df.sort_values(['folder_path', 'image_id'], inplace=True)
    fismo_df.reset_index(drop=True, inplace=True)
    # summary
    print(fismo_df.groupby(['class', 'purpose']).agg({'purpose': ['count']}))

    # freeze processing saving at csv
    save_dataframe(fismo_df, fismo_path)
# end prepare_fismo_df

def prepare_cairfire_df(cairfire_path):
    # CairFire fire
    fire_path = os.path.join(cairfire_path, 'fire')

    # fire dataframe
    fire_df = pd.DataFrame()
    fire_df['image_id'] = os.listdir(fire_path)
    fire_df['class'] = fire_label
    fire_df.insert(0, 'folder_path', 'fire')

    # fire dataset validation split
    test_qt = 51
    fire_df = split_dataframe(fire_df, test_qt)

    # CairFire no fire
    no_fire_path = os.path.join(cairfire_path, 'no_fire')

    # no fire dataframe
    no_fire_df = pd.DataFrame()
    no_fire_df['image_id'] = os.listdir(no_fire_path)
    no_fire_df['class'] = no_fire_label
    no_fire_df.insert(0, 'folder_path', 'no_fire')

    # fire dataset validation split
    test_qt = 51
    no_fire_df = split_dataframe(no_fire_df, test_qt)

    # concat splitted dataset
    cairfire_df = pd.concat([fire_df, no_fire_df])

    # order data reset
    cairfire_df.sort_values(['folder_path', 'image_id'], inplace=True)
    cairfire_df.reset_index(drop=True, inplace=True)

    # summary
    print(cairfire_df.groupby(['class', 'purpose']).agg({'purpose': ['count']}))

    # freeze processing saving at csv
    save_dataframe(cairfire_df, cairfire_path)
# end prepare_cairfire_df

def prepare_firenet_df(firenet_path):
    # FireNet fire
    fire_path = os.path.join(firenet_path, 'Training', 'Fire')

    # fire dataframe
    fire_df = pd.DataFrame()
    fire_df['image_id'] = os.listdir(fire_path)
    fire_df['class'] = fire_label
    fire_df.insert(0, 'folder_path', os.path.join('Training', 'Fire'))
    fire_df.drop_duplicates(subset='image_id', inplace=True)

    # fire dataset validation split
    test_size = .3
    test_qt = math.ceil(len(fire_df) * test_size)
    fire_df = split_dataframe(fire_df, test_qt)

    # FireNet no fire
    no_fire_path = os.path.join(firenet_dt, 'Training', 'NoFire')

    # fire dataframe
    no_fire_df = pd.DataFrame()
    no_fire_df['image_id'] = os.listdir(no_fire_path)
    no_fire_df['class'] = no_fire_label
    no_fire_df.insert(0, 'folder_path', os.path.join('Training', 'NoFire'))
    no_fire_df.drop_duplicates(subset='image_id', inplace=True)

    # no fire dataset validation split
    test_size = .3
    test_qt = math.ceil(len(no_fire_df) * test_size)
    no_fire_df = split_dataframe(no_fire_df, test_qt)

    # concat splitted dataset
    firenet_df = pd.concat([fire_df, no_fire_df])

    # order data reset
    firenet_df.sort_values(['folder_path', 'image_id'], inplace=True)
    firenet_df.reset_index(drop=True, inplace=True)

    # summary
    print(firenet_df.groupby(['class', 'purpose']).agg({'purpose': ['count']}))

    # freeze processing saving at csv
    save_dataframe(firenet_df, firenet_path)
# end prepare_firenet_df

def prepare_firenet_test_df(firenet_path):
    # FireNet test fire
    test_path = os.path.join(firenet_path, 'Test')
    fire_folders = glob.glob(os.path.join(test_path, 'Fire*'))

    # fire dataframe
    fire_df = pd.DataFrame(columns=['folder_path', 'image_id', 'class'])
    for fire_folder in fire_folders:
        fire_path = fire_folder.split(os.path.sep)[-1]
        # tmp storage
        tmp_df = pd.DataFrame()
        tmp_df['image_id'] = os.listdir(fire_folder)
        tmp_df['class'] = fire_label
        tmp_df.insert(0, 'folder_path', os.path.join('Test', fire_path))
        fire_df = pd.concat([fire_df, tmp_df])

    # FireNet test no fire
    no_fire_folders = glob.glob(os.path.join(test_path, 'NoFire*'))

    # fire dataframe
    no_fire_df = pd.DataFrame()
    for no_fire_folder in no_fire_folders:
        no_fire_path = no_fire_folder.split(os.path.sep)[-1]
        # tmp storage
        tmp_df = pd.DataFrame()
        tmp_df['image_id'] = os.listdir(no_fire_folder)
        tmp_df['class'] = no_fire_label
        tmp_df.insert(0, 'folder_path', os.path.join('Test', no_fire_path))
        no_fire_df = pd.concat([no_fire_df, tmp_df])

    # concat splitted dataset
    firenet_test_df = pd.concat([fire_df, no_fire_df])

    # order data reset
    firenet_test_df.sort_values(['folder_path', 'image_id'], inplace=True)
    firenet_test_df.reset_index(drop=True, inplace=True)

    # summary
    print(firenet_test_df['class'].value_counts())

    # freeze processing saving at csv
    save_dataframe(firenet_test_df, firenet_path, filename='test_dataset.csv')
# end prepare_firenet_df

def prepare_firesense_df(firesense_path):
    # frames extract
    # fire videos
    fs_path = os.path.join(firesense_path, 'fire')
    to_img_path = os.path.join(fs_path, 'imgs')
    extract_frames_to_folder(fs_path, prefix='fire', save_folder=to_img_path)
    # no fire videos
    fs_path = os.path.join(firesense_path, 'no_fire')
    to_img_path = os.path.join(fs_path, 'imgs')
    extract_frames_to_folder(fs_path, prefix='no_fire', save_folder=to_img_path)

    # FireSense fire
    fire_path = os.path.join(firesense_path, 'fire', 'imgs')

    # fire dataframe
    fire_df = pd.DataFrame()
    fire_df['image_id'] = os.listdir(fire_path)
    fire_df['class'] = fire_label
    fire_df.insert(0, 'folder_path', os.path.join('fire', 'imgs'))
    fire_df.drop_duplicates(subset='image_id', inplace=True)

    # fire dataset validation split
    test_size = .2
    test_qt = math.ceil(len(fire_df) * test_size)
    fire_df = split_dataframe(fire_df, test_qt)

    # FireSense no fire
    no_fire_path = os.path.join(firesense_path, 'no_fire', 'imgs')

    # fire dataframe
    no_fire_df = pd.DataFrame()
    no_fire_df['image_id'] = os.listdir(no_fire_path)
    no_fire_df['class'] = no_fire_label
    no_fire_df.insert(0, 'folder_path', os.path.join('no_fire', 'imgs'))
    no_fire_df.drop_duplicates(subset='image_id', inplace=True)

    # fire dataset validation split
    test_size = .2
    test_qt = math.ceil(len(no_fire_df) * test_size)
    no_fire_df = split_dataframe(no_fire_df, test_qt)

    # concat splitted dataset
    firesense_df = pd.concat([fire_df, no_fire_df])

    # order data reset
    firesense_df.sort_values(['folder_path', 'image_id'], inplace=True)
    firesense_df.reset_index(drop=True, inplace=True)

    # summary
    print(firesense_df.groupby(['class', 'purpose']).agg({'purpose': ['count']}))

    # freeze processing saving at csv
    save_dataframe(firesense_df, firesense_path)
# end prepare_firesense_df

if __name__ == '__main__':
    root_path = os.getcwd()
    print('Root path in', root_path)

    datasets_root = os.path.join(root_path, '..', 'datasets')

    fismo_dt = os.path.join(datasets_root, 'FiSmo-Images')
    firenet_dt = os.path.join(datasets_root, 'FireNetDataset')
    firesense_dt = os.path.join(datasets_root, 'FireSenseDataset')
    cairfire_dt = os.path.join(datasets_root, 'CairDataset')

    prepare_fismo_df(fismo_dt)
    prepare_firenet_df(firenet_dt)
    prepare_cairfire_df(cairfire_dt)
    prepare_firesense_df(firesense_dt)
